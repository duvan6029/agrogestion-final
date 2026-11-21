"""Presentación web. La autorización se comprueba en el servidor en cada petición."""
import os
import io
import csv
import sqlite3
import secrets
import time
from pathlib import Path
from functools import wraps
from datetime import date
from flask import Flask, render_template, request, session, redirect, url_for, flash, send_file, abort
from core import AgroServicio, ReglaError, MAESTROS, INFORMES, cop, hash_clave, verificar

MOVIMIENTOS={
 'siembras': [('lote','Lote','lotes'),('cultivo','Cultivo','cultivos'),('fecha','Fecha de siembra','date'),('area','Área (ha)','number'),('semilla','Cantidad de semilla','number'),('responsable','Responsable','text')],
 'compras': [('insumo','Insumo','insumos'),('proveedor','Proveedor','proveedores'),('fecha','Fecha','date'),('cantidad','Cantidad','number'),('unitario','Precio por unidad (COP)','number')],
 'aplicaciones': [('siembra','Siembra','siembras'),('insumo','Insumo','insumos'),('fecha','Fecha','date'),('cantidad','Cantidad','number'),('responsable','Responsable','text')],
 'cosechas': [('siembra','Siembra','siembras'),('fecha','Fecha','date'),('cantidad','Producción obtenida','number'),('calidad','Calidad','calidades')],
 'ventas': [('cosecha','Cosecha','cosechas'),('fecha','Fecha','date'),('comprador','Comprador','text'),('cantidad','Cantidad vendida','number'),('unitario','Precio por unidad (COP)','number')],
 'costos': [('siembra','Siembra','siembras'),('fecha','Fecha','date'),('categoria','Categoría','categorias'),('concepto','Concepto','text'),('valor','Valor (COP)','number')]
}
TITULOS={'fincas':'Fincas','lotes':'Lotes','cultivos':'Cultivos','proveedores':'Proveedores','insumos':'Insumos','usuarios':'Usuarios','siembras':'Siembras','compras':'Compras de insumos','aplicaciones':'Aplicaciones','cosechas':'Cosechas','ventas':'Ventas','costos':'Costos adicionales'}

def create_app(db_path=None, testing=False):
    app=Flask(__name__)
    carpeta=Path(__file__).parent/'datos'; carpeta.mkdir(exist_ok=True)
    clave=carpeta/'sesion.key'
    if not clave.exists(): clave.write_text(secrets.token_hex(32))
    app.config.update(SECRET_KEY=os.environ.get('AGRO_SECRET',clave.read_text()),TESTING=testing,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',SESSION_COOKIE_SECURE=os.environ.get('AGRO_HTTPS')=='1',MAX_CONTENT_LENGTH=1024*1024)
    servicio=AgroServicio(db_path or carpeta/'agrogestion.sqlite'); servicio.inicializar()
    app.servicio=servicio
    app.jinja_env.filters['cop']=cop
    ultimo_respaldo=[None]

    def usuario():
        if not session.get('uid'): return None
        filas=servicio.filas('SELECT id,nombre,rol,activo FROM usuarios WHERE id=?',(session['uid'],))
        return filas[0] if filas and filas[0]['activo'] else None

    @app.before_request
    def seguridad():
        if not testing and ultimo_respaldo[0]!=date.today():
            servicio.respaldo(carpeta/'respaldos'); ultimo_respaldo[0]=date.today()
        if session.get('uid'):
            if time.time()-session.get('ultima',0)>900:
                session.clear(); flash('La sesión venció por 15 minutos de inactividad.','aviso')
            else: session['ultima']=time.time()
        if 'csrf' not in session: session['csrf']=secrets.token_hex(24)
        if request.method=='POST' and not secrets.compare_digest(request.form.get('csrf',''),session['csrf']): abort(400)

    def acceso(*roles):
        def decorar(func):
            @wraps(func)
            def envuelto(*a,**kw):
                u=usuario()
                if not u: return redirect(url_for('login'))
                if roles and u['rol'] not in roles: abort(403)
                return func(*a,**kw)
            return envuelto
        return decorar

    def opciones():
        op={'roles':[('Administrador','Administrador'),('Operario','Operario'),('Consultor','Consultor')],'calidades':[(x,x) for x in ['Primera','Segunda','Descarte']],'categorias':[(x,x) for x in ['Mano de obra','Maquinaria','Transporte','Otros']]}
        for tabla in MAESTROS:
            if tabla=='usuarios': continue
            op[tabla]=[(r['id'],r['nombre']+(' · '+r['variedad'] if tabla=='cultivos' else '')+(' · finca #'+str(r['finca']) if tabla=='lotes' else '')+(' · '+r['unidad'] if tabla=='insumos' else '')) for r in servicio.filas(f'SELECT * FROM {tabla} WHERE activo=1')]
        op['siembras']=[(r['id'],f"#{r['id']} · {r['lote']} / {r['cultivo']} · {r['estado']}") for r in servicio.filas('SELECT s.id,l.nombre lote,c.nombre cultivo,s.estado FROM siembras s JOIN lotes l ON l.id=s.lote JOIN cultivos c ON c.id=s.cultivo')]
        op['cosechas']=[(r['id'],f"#{r['id']} · siembra {r['siembra']} · {r['cantidad']} {r['unidad']} · {r['calidad']}") for r in servicio.filas('SELECT * FROM cosechas')]
        return op

    @app.context_processor
    def contexto(): return dict(u=usuario(),titulos=TITULOS,csrf=session.get('csrf'),hoy=date.today().isoformat())

    @app.route('/login',methods=['GET','POST'])
    def login():
        if request.method=='POST':
            if time.time()<session.get('bloqueo',0):
                flash('Espere un minuto antes de intentar nuevamente.','error'); return render_template('login.html'),429
            rows=servicio.filas('SELECT * FROM usuarios WHERE nombre=? AND activo=1',(request.form.get('nombre',''),))
            if rows and verificar(request.form.get('clave',''),rows[0]['clave']):
                session.clear(); session.update(uid=rows[0]['id'],ultima=time.time(),csrf=secrets.token_hex(24)); return redirect('/')
            session['fallos']=session.get('fallos',0)+1
            if session['fallos']>=5: session['bloqueo']=time.time()+60; session['fallos']=0
            flash('Usuario o contraseña incorrectos.','error')
        return render_template('login.html')

    @app.post('/salir')
    def salir(): session.clear(); return redirect('/login')

    @app.get('/')
    @acceso()
    def inicio():
        siembras=servicio.filas("SELECT COUNT(*) n FROM siembras WHERE estado='En desarrollo'")[0]['n']
        alertas=servicio.filas('SELECT mensaje FROM alertas') if usuario()['rol']=='Administrador' else []
        utilidad=INFORMES['rentabilidad'](servicio).generar({})['filas']
        return render_template('inicio.html',activas=siembras,alertas=alertas,utilidad=sum(r['Utilidad_COP'] for r in utilidad),lotes=servicio.filas('SELECT COUNT(*) n FROM lotes WHERE activo=1')[0]['n'],recientes=servicio.filas('SELECT fecha,usuario,tipo,detalle FROM eventos ORDER BY id DESC LIMIT 8') if usuario()['rol']=='Administrador' else [])

    @app.route('/maestros/<tabla>',methods=['GET','POST'])
    @acceso('Administrador')
    def maestro(tabla):
        if tabla not in MAESTROS: abort(404)
        editar=request.args.get('editar',type=int)
        actual={}
        if editar:
            rows=servicio.filas(f'SELECT * FROM {tabla} WHERE id=?',(editar,))
            if not rows: abort(404)
            actual=rows[0]; actual.pop('clave',None)
        if request.method=='POST':
            try:
                if request.form.get('accion')=='desactivar': servicio.desactivar(tabla,int(request.form['id']),usuario()['nombre'])
                else: servicio.guardar(tabla,request.form,usuario()['nombre'],editar)
                flash('Registro guardado correctamente.','exito'); return redirect(url_for('maestro',tabla=tabla))
            except (ReglaError,sqlite3.IntegrityError,ValueError) as e:
                flash(str(e) if not isinstance(e,sqlite3.IntegrityError) else 'El nombre o correo ya existe, o la referencia no es válida.','error'); actual=dict(request.form)
        rows=servicio.filas(f'SELECT * FROM {tabla} ORDER BY id DESC')
        for r in rows: r.pop('clave',None)
        return render_template('gestion.html',titulo=TITULOS[tabla],tabla=tabla,fields=MAESTROS[tabla],opciones=opciones(),actual=actual,rows=rows,maestro=True,puede=True,editar=editar)

    @app.route('/movimientos/<tabla>',methods=['GET','POST'])
    @acceso()
    def movimiento(tabla):
        if tabla not in MOVIMIENTOS: abort(404)
        rol=usuario()['rol']; puede=rol in ('Administrador','Operario') and not (tabla in ('compras','ventas') and rol!='Administrador')
        # El consultor accede por informes. El operario no consulta precios de venta/compras.
        if rol=='Consultor' or (tabla in ('compras','ventas') and rol!='Administrador'): abort(403)
        if request.method=='POST':
            if not puede: abort(403)
            try:
                if request.form.get('accion')=='estado': servicio.estado(int(request.form['id']),request.form['estado'],request.form['observacion'],usuario()['nombre'])
                else: servicio.registrar(tabla,request.form,usuario()['nombre'])
                flash('Operación registrada.','exito'); return redirect(url_for('movimiento',tabla=tabla))
            except (ReglaError,sqlite3.IntegrityError,ValueError,KeyError) as e: flash(str(e) if not isinstance(e,sqlite3.IntegrityError) else 'Operación inválida o lote ya ocupado.','error')
        rows=servicio.filas(f'SELECT * FROM {tabla} ORDER BY id DESC')
        return render_template('gestion.html',titulo=TITULOS[tabla],tabla=tabla,fields=MOVIMIENTOS[tabla],opciones=opciones(),actual=dict(request.form) if request.method=='POST' else {},rows=rows,maestro=False,puede=puede)

    @app.get('/informes/<tipo>')
    @acceso()
    def informe(tipo):
        if usuario()['rol']=='Operario': abort(403)
        if tipo not in INFORMES: abort(404)
        try: resultado=INFORMES[tipo](servicio).generar(request.args)
        except ReglaError as e: flash(str(e),'error'); resultado=dict(titulo=INFORMES[tipo].titulo,filas=[],columnas=[],cantidad=0,mensaje=str(e))
        formato=request.args.get('formato')
        if formato in ('pdf','xlsx'): return exportar(resultado,formato)
        return render_template('informes.html',resultado=resultado,tipo=tipo,opciones=opciones(),filtros=request.args)

    @app.get('/respaldo')
    @acceso('Administrador')
    def respaldo(): return send_file(servicio.respaldo(carpeta/'respaldos'),as_attachment=True)

    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(400)
    def error(e): return render_template('error.html',codigo=e.code),e.code
    return app

def exportar(resultado,formato):
    columnas=resultado['columnas']; filas=resultado['filas']; buffer=io.BytesIO()
    if formato=='xlsx':
        from openpyxl import Workbook
        from openpyxl.styles import Font,PatternFill
        from openpyxl.utils import get_column_letter
        wb=Workbook(); ws=wb.active; ws.title='Informe'
        ws.append([resultado['titulo']]); ws.append(columnas or ['Sin resultados'])
        for r in filas: ws.append([("'"+str(v)) if isinstance(v,str) and v.startswith(('=','+','-','@')) else v for v in r.values()])
        resumen=wb.create_sheet('Resumen')
        resumen.append(['Indicador','Total COP'])
        for k,v in resultado.get('totales',{}).items(): resumen.append([k,v])
        resumen.column_dimensions['A'].width=35
        resumen.column_dimensions['B'].width=22
        for c in ws[2]: c.font=Font(bold=True,color='FFFFFF'); c.fill=PatternFill('solid',fgColor='315740')
        for i,col in enumerate(columnas,1): ws.column_dimensions[get_column_letter(i)].width=min(36,max(18,len(col)+3))
        ws.freeze_panes='A3'; ws.auto_filter.ref=f'A2:{get_column_letter(max(1,len(columnas)))}{max(2,ws.max_row)}'; wb.save(buffer)
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    else:
        from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer
        from reportlab.lib.pagesizes import A3,landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        from xml.sax.saxutils import escape
        styles=getSampleStyleSheet(); styles['BodyText'].fontSize=8; styles['BodyText'].leading=10
        doc=SimpleDocTemplate(buffer,pagesize=landscape(A3),rightMargin=24,leftMargin=24,topMargin=24,bottomMargin=24)
        story=[Paragraph('AgroGestión — '+resultado['titulo'],styles['Title']),Paragraph('Generado: '+date.today().isoformat()+' · COP cuando se indica · '+str(len(filas))+' registros',styles['Normal']),Spacer(1,16)]
        if filas:
            datos=[[Paragraph(escape(str(c)),styles['BodyText']) for c in columnas]]+[[Paragraph(escape('—' if v is None else str(v)),styles['BodyText']) for v in r.values()] for r in filas]
            t=Table(datos,repeatRows=1,colWidths=[(landscape(A3)[0]-48)/len(columnas)]*len(columnas)); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dce9df')),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#ccd5cc')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),7)])); story.append(t)
        else: story.append(Paragraph('Sin resultados.',styles['Normal']))
        if resultado.get('totales'):
            story.append(Spacer(1,14))
            for k,v in resultado['totales'].items():
                story.append(Paragraph(escape(k.replace('_',' ')+': '+cop(round(v*100))),styles['Normal']))
        doc.build(story); mime='application/pdf'
    buffer.seek(0)
    return send_file(buffer,mimetype=mime,as_attachment=True,download_name='AgroGestion_'+resultado['titulo'].replace(' ','_')+'.'+formato)

if __name__=='__main__':
    app=create_app()
    print('AgroGestión: http://127.0.0.1:5000 (Ctrl+C para detener)')
    app.run(host='127.0.0.1',port=int(os.environ.get('AGRO_PORT','5000')),debug=False)
