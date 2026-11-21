"""Dominio, persistencia y patrones de AgroGestión. Importes en centavos COP."""
import sqlite3
import hashlib
import secrets
import json
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from abc import ABC, abstractmethod

class ReglaError(ValueError):
    pass

class Conexion(sqlite3.Connection):
    def __exit__(self, *args):
        try: return super().__exit__(*args)
        finally: self.close()

def numero(valor, positivo=True):
    try:
        n = Decimal(str(valor))
        if not n.is_finite() or (n <= 0 if positivo else n < 0): raise ValueError()
        return n
    except Exception:
        raise ReglaError('Ingrese un número válido ' + ('mayor que cero.' if positivo else 'no negativo.'))

def dinero(valor):
    return int((numero(valor, False)*100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

def cop(centavos):
    return '$ ' + f'{centavos/100:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')

def fecha(valor):
    try: return date.fromisoformat(valor)
    except Exception: raise ReglaError('La fecha debe ser válida (AAAA-MM-DD).')

def hash_clave(clave, sal=None):
    sal = sal or secrets.token_hex(16)
    return sal + ':' + hashlib.pbkdf2_hmac('sha256', clave.encode(), sal.encode(), 260000).hex()

def verificar(clave, guardada):
    sal = guardada.split(':')[0]
    return secrets.compare_digest(hash_clave(clave, sal), guardada)

# OBSERVER: contrato del observador y sujeto con suscripción dinámica.
class Observador(ABC):
    @abstractmethod
    def actualizar(self, evento, db): pass

class EventosInventario:
    def __init__(self): self.observadores = []
    def suscribir(self, observador):
        if observador not in self.observadores: self.observadores.append(observador)
    def retirar(self, observador):
        if observador in self.observadores: self.observadores.remove(observador)
    def notificar(self, evento, db):
        for observador in tuple(self.observadores): observador.actualizar(evento, db)

class AlertaStock(Observador):
    def actualizar(self, evento, db):
        # El observador persiste o resuelve la alerta dentro de la MISMA transacción.
        item = db.execute('SELECT * FROM insumos WHERE id=?', (evento['insumo'],)).fetchone()
        db.execute('DELETE FROM alertas WHERE insumo=?', (item['id'],))
        if item['activo'] and item['stock'] <= item['minimo']:
            db.execute('INSERT INTO alertas(insumo,mensaje) VALUES (?,?)',
                       (item['id'], f"{item['nombre']}: stock {item['stock']:g} {item['unidad']}; mínimo {item['minimo']:g}"))

class AuditorInventario(Observador):
    def actualizar(self, evento, db):
        db.execute('INSERT INTO eventos(fecha,usuario,tipo,detalle) VALUES (?,?,?,?)',
                   (datetime.now().isoformat(timespec='seconds'), evento['usuario'], evento['tipo'], f"Insumo #{evento['insumo']}: {evento['tipo']}"))

SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS usuarios(id INTEGER PRIMARY KEY,nombre TEXT NOT NULL COLLATE NOCASE UNIQUE,email TEXT NOT NULL COLLATE NOCASE UNIQUE,clave TEXT NOT NULL,rol TEXT NOT NULL CHECK(rol IN ('Administrador','Operario','Consultor')),activo INTEGER NOT NULL DEFAULT 1,creado TEXT,modificado TEXT,autor TEXT);
CREATE TABLE IF NOT EXISTS fincas(id INTEGER PRIMARY KEY,nombre TEXT NOT NULL COLLATE NOCASE UNIQUE,ubicacion TEXT NOT NULL,area REAL NOT NULL,suelo TEXT NOT NULL,activo INTEGER DEFAULT 1,creado TEXT,modificado TEXT,autor TEXT);
CREATE TABLE IF NOT EXISTS lotes(id INTEGER PRIMARY KEY,finca INTEGER REFERENCES fincas(id),nombre TEXT NOT NULL COLLATE NOCASE,ubicacion TEXT NOT NULL,area REAL NOT NULL,suelo TEXT NOT NULL,activo INTEGER DEFAULT 1,creado TEXT,modificado TEXT,autor TEXT,UNIQUE(finca,nombre));
CREATE TABLE IF NOT EXISTS cultivos(id INTEGER PRIMARY KEY,nombre TEXT NOT NULL COLLATE NOCASE,variedad TEXT NOT NULL,ciclo INTEGER NOT NULL,unidad TEXT NOT NULL,activo INTEGER DEFAULT 1,creado TEXT,modificado TEXT,autor TEXT,UNIQUE(nombre,variedad));
CREATE TABLE IF NOT EXISTS proveedores(id INTEGER PRIMARY KEY,nombre TEXT NOT NULL COLLATE NOCASE UNIQUE,contacto TEXT NOT NULL,activo INTEGER DEFAULT 1,creado TEXT,modificado TEXT,autor TEXT);
CREATE TABLE IF NOT EXISTS insumos(id INTEGER PRIMARY KEY,nombre TEXT NOT NULL COLLATE NOCASE UNIQUE,categoria TEXT NOT NULL,unidad TEXT NOT NULL,minimo REAL NOT NULL,stock REAL NOT NULL DEFAULT 0,valor INTEGER NOT NULL DEFAULT 0,activo INTEGER DEFAULT 1,creado TEXT,modificado TEXT,autor TEXT);
CREATE TABLE IF NOT EXISTS siembras(id INTEGER PRIMARY KEY,lote INTEGER REFERENCES lotes(id),cultivo INTEGER REFERENCES cultivos(id),fecha TEXT NOT NULL,area REAL NOT NULL,semilla REAL NOT NULL,responsable TEXT NOT NULL,estimada TEXT NOT NULL,estado TEXT NOT NULL DEFAULT 'En desarrollo',observacion TEXT DEFAULT '',creado TEXT,modificado TEXT,autor TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS lote_ocupado ON siembras(lote) WHERE estado='En desarrollo';
CREATE TABLE IF NOT EXISTS compras(id INTEGER PRIMARY KEY,insumo INTEGER REFERENCES insumos(id),proveedor INTEGER REFERENCES proveedores(id),fecha TEXT NOT NULL,cantidad REAL NOT NULL,unitario INTEGER NOT NULL,total INTEGER NOT NULL,creado TEXT,modificado TEXT,autor TEXT);
CREATE TABLE IF NOT EXISTS aplicaciones(id INTEGER PRIMARY KEY,siembra INTEGER REFERENCES siembras(id),insumo INTEGER REFERENCES insumos(id),fecha TEXT NOT NULL,cantidad REAL NOT NULL,costo INTEGER NOT NULL,responsable TEXT NOT NULL,creado TEXT,modificado TEXT,autor TEXT);
CREATE TABLE IF NOT EXISTS cosechas(id INTEGER PRIMARY KEY,siembra INTEGER REFERENCES siembras(id),fecha TEXT NOT NULL,cantidad REAL NOT NULL,unidad TEXT NOT NULL,calidad TEXT NOT NULL,creado TEXT,modificado TEXT,autor TEXT);
CREATE TABLE IF NOT EXISTS ventas(id INTEGER PRIMARY KEY,cosecha INTEGER REFERENCES cosechas(id),fecha TEXT NOT NULL,comprador TEXT NOT NULL,cantidad REAL NOT NULL,unitario INTEGER NOT NULL,total INTEGER NOT NULL,creado TEXT,modificado TEXT,autor TEXT);
CREATE TABLE IF NOT EXISTS costos(id INTEGER PRIMARY KEY,siembra INTEGER REFERENCES siembras(id),fecha TEXT NOT NULL,categoria TEXT NOT NULL,concepto TEXT NOT NULL,valor INTEGER NOT NULL,creado TEXT,modificado TEXT,autor TEXT);
CREATE TABLE IF NOT EXISTS alertas(insumo INTEGER PRIMARY KEY REFERENCES insumos(id),mensaje TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS eventos(id INTEGER PRIMARY KEY,fecha TEXT,usuario TEXT,tipo TEXT,detalle TEXT);
'''

MAESTROS = {
 'fincas': [('nombre','Nombre','text'),('ubicacion','Ubicación','text'),('area','Área (ha)','number'),('suelo','Tipo de suelo','text')],
 'lotes': [('finca','Finca','fincas'),('nombre','Nombre','text'),('ubicacion','Ubicación','text'),('area','Área (ha)','number'),('suelo','Tipo de suelo','text')],
 'cultivos': [('nombre','Nombre','text'),('variedad','Variedad','text'),('ciclo','Ciclo (días)','number'),('unidad','Unidad de producción','text')],
 'proveedores': [('nombre','Nombre','text'),('contacto','Contacto','text')],
 'insumos': [('nombre','Nombre','text'),('categoria','Categoría','text'),('unidad','Unidad','text'),('minimo','Stock mínimo','number')],
 'usuarios': [('nombre','Usuario','text'),('email','Correo','email'),('rol','Rol','roles'),('clave','Contraseña (8 o más caracteres)','password')]
}

class AgroServicio:
    def __init__(self, ruta):
        self.ruta = str(ruta)
        self.eventos = EventosInventario()
        self.eventos.suscribir(AlertaStock())
        self.eventos.suscribir(AuditorInventario())
    def conectar(self):
        db = sqlite3.connect(self.ruta, timeout=15, factory=Conexion)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db
    def inicializar(self):
        Path(self.ruta).parent.mkdir(parents=True,exist_ok=True)
        with self.conectar() as db:
            db.executescript(SCHEMA)
            for tabla in list(MAESTROS)+['siembras','compras','aplicaciones','cosechas','ventas','costos']:
                if 'creador' not in [c[1] for c in db.execute(f'PRAGMA table_info({tabla})')]:
                    db.execute(f'ALTER TABLE {tabla} ADD COLUMN creador TEXT')
    def filas(self, sql, args=()):
        with self.conectar() as db: return [dict(x) for x in db.execute(sql,args)]
    def auditoria(self, db, usuario, tipo, detalle):
        db.execute('INSERT INTO eventos(fecha,usuario,tipo,detalle) VALUES (?,?,?,?)',
                   (datetime.now().isoformat(timespec='seconds'),usuario,tipo,detalle))
    def activo(self, db, tabla, ident):
        row = db.execute(f'SELECT * FROM {tabla} WHERE id=?',(ident,)).fetchone()
        if not row or not row['activo']: raise ReglaError('El registro seleccionado no está activo.')
        return row
    def guardar(self, tabla, datos, usuario, ident=None):
        if tabla not in MAESTROS: raise ReglaError('Entidad no permitida.')
        d = {}
        for campo,_,tipo in MAESTROS[tabla]:
            valor = str(datos.get(campo,'')).strip()
            if campo == 'clave' and ident and not valor: continue
            if not valor: raise ReglaError('Todos los campos son obligatorios.')
            d[campo] = valor
        if 'area' in d: d['area'] = float(numero(d['area']))
        if 'minimo' in d: d['minimo'] = float(numero(d['minimo'],False))
        if 'ciclo' in d:
            n=numero(d['ciclo'])
            if n != int(n): raise ReglaError('El ciclo debe ser un entero positivo.')
            d['ciclo']=int(n)
        if tabla=='usuarios':
            if d['rol'] not in ['Administrador','Operario','Consultor']: raise ReglaError('Rol no válido.')
            if '@' not in d['email']: raise ReglaError('Correo no válido.')
            if 'clave' in d:
                if len(d['clave'])<8: raise ReglaError('La contraseña requiere al menos 8 caracteres.')
                d['clave']=hash_clave(d['clave'])
        now=datetime.now().isoformat(timespec='seconds')
        with self.conectar() as db:
            if tabla=='lotes':
                finca=self.activo(db,'fincas',d['finca'])
                otras=db.execute('SELECT COALESCE(SUM(area),0) FROM lotes WHERE finca=? AND activo=1 AND id<>?',(d['finca'],ident or 0)).fetchone()[0]
                if otras+d['area']>finca['area']+1e-8: raise ReglaError('El área de los lotes supera el área de la finca.')
            if ident:
                original=self.activo(db,tabla,ident)
                if tabla=='usuarios' and original['rol']=='Administrador' and d['rol']!='Administrador':
                    if db.execute("SELECT COUNT(*) FROM usuarios WHERE activo=1 AND rol='Administrador'").fetchone()[0]<=1: raise ReglaError('Debe conservar al menos un administrador.')
                if tabla in ('fincas','lotes'):
                    usado=db.execute('SELECT COALESCE(SUM(area),0) FROM lotes WHERE finca=? AND activo=1',(ident,)).fetchone()[0] if tabla=='fincas' else db.execute('SELECT COALESCE(MAX(area),0) FROM siembras WHERE lote=?',(ident,)).fetchone()[0]
                    if d['area']<usado: raise ReglaError('El área es menor que la ya registrada.')
                if tabla=='lotes' and str(original['finca'])!=str(d['finca']) and db.execute('SELECT 1 FROM siembras WHERE lote=?',(ident,)).fetchone(): raise ReglaError('Un lote con historial no puede cambiar de finca.')
                if tabla=='cultivos' and original['unidad']!=d['unidad'] and db.execute('SELECT 1 FROM siembras WHERE cultivo=?',(ident,)).fetchone(): raise ReglaError('La unidad no puede cambiar si existe historial.')
                if tabla=='insumos' and original['unidad']!=d['unidad'] and (original['stock'] or db.execute('SELECT 1 FROM compras WHERE insumo=?',(ident,)).fetchone()): raise ReglaError('La unidad de un insumo con movimientos no puede cambiar.')
                d.update(modificado=now,autor=usuario)
                db.execute(f"UPDATE {tabla} SET {','.join(k+'=?' for k in d)} WHERE id=?",(*d.values(),ident))
            else:
                d.update(creado=now,modificado=now,autor=usuario,creador=usuario)
                ident=db.execute(f"INSERT INTO {tabla} ({','.join(d)}) VALUES ({','.join('?' for _ in d)})",tuple(d.values())).lastrowid
            self.auditoria(db,usuario,'Maestro',f'{tabla} #{ident}: guardado')
            if tabla=='insumos': self.eventos.notificar(dict(insumo=ident,usuario=usuario,tipo='Configuración de stock'),db)
        return ident
    def desactivar(self,tabla,ident,usuario):
        if tabla not in MAESTROS: raise ReglaError('Entidad no permitida.')
        with self.conectar() as db:
            actual=self.activo(db,tabla,ident)
            if tabla=='usuarios' and actual['nombre']==usuario: raise ReglaError('No puede desactivar su propia cuenta.')
            if tabla=='usuarios' and actual['rol']=='Administrador' and db.execute("SELECT COUNT(*) FROM usuarios WHERE activo=1 AND rol='Administrador'").fetchone()[0]<=1: raise ReglaError('Debe conservar un administrador.')
            if tabla in ('lotes','fincas'):
                sql="SELECT 1 FROM siembras s JOIN lotes l ON l.id=s.lote WHERE s.estado='En desarrollo' AND "+('l.id=?' if tabla=='lotes' else 'l.finca=?')
                if db.execute(sql,(ident,)).fetchone(): raise ReglaError('Hay siembras activas asociadas.')
            db.execute(f'UPDATE {tabla} SET activo=0,modificado=?,autor=? WHERE id=?',(datetime.now().isoformat(),usuario,ident))
            self.auditoria(db,usuario,'Desactivación',f'{tabla} #{ident}')
    def registrar(self,tipo,d,usuario):
        now=datetime.now().isoformat(timespec='seconds')
        campos=dict(creado=now,modificado=now,autor=usuario,creador=usuario)
        with self.conectar() as db:
            db.execute('BEGIN IMMEDIATE')
            f=fecha(d.get('fecha',''))
            if f>date.today(): raise ReglaError('La fecha no puede ser futura.')
            campos['fecha']=f.isoformat()
            if tipo=='siembras':
                lote=self.activo(db,'lotes',d['lote']); self.activo(db,'fincas',lote['finca']); cultivo=self.activo(db,'cultivos',d['cultivo'])
                if db.execute("SELECT 1 FROM siembras WHERE lote=? AND estado='En desarrollo'",(lote['id'],)).fetchone(): raise ReglaError('El lote ya tiene una siembra activa.')
                area=numero(d['area'])
                if area>Decimal(str(lote['area'])): raise ReglaError('El área sembrada supera la del lote.')
                campos.update(lote=lote['id'],cultivo=cultivo['id'],area=float(area),semilla=float(numero(d['semilla'])),responsable=d.get('responsable','').strip(),estimada=(f+timedelta(days=cultivo['ciclo'])).isoformat())
            elif tipo=='compras':
                ins=self.activo(db,'insumos',d['insumo']); prov=self.activo(db,'proveedores',d['proveedor'])
                cant=numero(d['cantidad']); unit=dinero(d['unitario']); total=int((cant*unit).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
                campos.update(insumo=ins['id'],proveedor=prov['id'],cantidad=float(cant),unitario=unit,total=total)
                db.execute('UPDATE insumos SET stock=stock+?,valor=valor+?,modificado=?,autor=? WHERE id=?',(float(cant),total,now,usuario,ins['id']))
            elif tipo in ('aplicaciones','cosechas','costos'):
                siembra=db.execute('SELECT * FROM siembras WHERE id=?',(d['siembra'],)).fetchone()
                if not siembra: raise ReglaError('Siembra inexistente.')
                if f<fecha(siembra['fecha']): raise ReglaError('La fecha precede a la siembra.')
                campos['siembra']=siembra['id']
                if tipo=='aplicaciones':
                    if siembra['estado']!='En desarrollo': raise ReglaError('La siembra está cerrada; no admite aplicaciones.')
                    ins=self.activo(db,'insumos',d['insumo']); cant=numero(d['cantidad']); stock=Decimal(str(ins['stock']))
                    if cant>stock: raise ReglaError('Stock insuficiente. No se registró la aplicación.')
                    costo=ins['valor'] if cant==stock else int((cant*Decimal(ins['valor'])/stock).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
                    campos.update(insumo=ins['id'],cantidad=float(cant),costo=costo,responsable=d.get('responsable','').strip())
                    db.execute('UPDATE insumos SET stock=?,valor=valor-?,modificado=?,autor=? WHERE id=?',(float(stock-cant),costo,now,usuario,ins['id']))
                elif tipo=='cosechas':
                    if siembra['estado']!='En desarrollo': raise ReglaError('La siembra está cerrada. Registre las cosechas parciales antes de cerrarla.')
                    calidad=d['calidad']
                    if calidad not in ['Primera','Segunda','Descarte']: raise ReglaError('Calidad no válida.')
                    unidad=db.execute('SELECT unidad FROM cultivos WHERE id=?',(siembra['cultivo'],)).fetchone()[0]
                    campos.update(cantidad=float(numero(d['cantidad'])),unidad=unidad,calidad=calidad)
                else:
                    if d['categoria'] not in ['Mano de obra','Maquinaria','Transporte','Otros']: raise ReglaError('Categoría no válida.')
                    campos.update(categoria=d['categoria'],concepto=d.get('concepto','').strip(),valor=dinero(d['valor']))
            elif tipo=='ventas':
                cosecha=db.execute('SELECT * FROM cosechas WHERE id=?',(d['cosecha'],)).fetchone()
                if not cosecha: raise ReglaError('Cosecha inexistente.')
                if cosecha['calidad']=='Descarte': raise ReglaError('La producción de descarte no se vende.')
                if f<fecha(cosecha['fecha']): raise ReglaError('La venta no puede preceder a la cosecha.')
                vendido=db.execute('SELECT COALESCE(SUM(cantidad),0) FROM ventas WHERE cosecha=?',(cosecha['id'],)).fetchone()[0]
                cant=numero(d['cantidad'])
                if cant>Decimal(str(cosecha['cantidad']))-Decimal(str(vendido)): raise ReglaError('La venta supera la cosecha disponible.')
                unit=dinero(d['unitario']); campos.update(cosecha=cosecha['id'],cantidad=float(cant),unitario=unit,total=int((cant*unit).quantize(Decimal('1'),rounding=ROUND_HALF_UP)),comprador=d.get('comprador','').strip())
            else: raise ReglaError('Movimiento no permitido.')
            for key in ('responsable','concepto','comprador'):
                if key in campos and not campos[key]: raise ReglaError('Complete los campos de texto obligatorios.')
            ident=db.execute(f"INSERT INTO {tipo} ({','.join(campos)}) VALUES ({','.join('?' for _ in campos)})",tuple(campos.values())).lastrowid
            self.auditoria(db,usuario,tipo,f'Registro #{ident}')
            if tipo in ('compras','aplicaciones'):
                self.eventos.notificar(dict(insumo=campos['insumo'],usuario=usuario,tipo=tipo),db)
            return ident
    def estado(self,ident,estado,observacion,usuario):
        if estado not in ['Cosechada','Perdida'] or not observacion.strip(): raise ReglaError('Seleccione estado final e indique la observación.')
        with self.conectar() as db:
            s=db.execute('SELECT * FROM siembras WHERE id=?',(ident,)).fetchone()
            if not s or s['estado']!='En desarrollo': raise ReglaError('La siembra ya está cerrada o no existe.')
            if estado=='Cosechada' and not db.execute('SELECT 1 FROM cosechas WHERE siembra=?',(ident,)).fetchone(): raise ReglaError('Registre una cosecha antes de cerrar como cosechada.')
            db.execute('UPDATE siembras SET estado=?,observacion=?,modificado=?,autor=? WHERE id=?',(estado,observacion.strip(),datetime.now().isoformat(),usuario,ident))
            self.auditoria(db,usuario,'Estado',f'Siembra #{ident}: {estado}. {observacion}')
    def respaldo(self,carpeta):
        carpeta=Path(carpeta); carpeta.mkdir(parents=True,exist_ok=True)
        ruta=carpeta/('agrogestion-'+date.today().isoformat()+'.sqlite')
        with self.conectar() as db, sqlite3.connect(ruta,factory=Conexion) as destino: db.backup(destino)
        return ruta

# TEMPLATE METHOD: generar fija el algoritmo; cada informe redefine solo consultar.
class InformePlantilla(ABC):
    titulo=''
    def __init__(self,servicio): self.servicio=servicio
    def generar(self,filtros):
        filtros={k:str(v).strip() for k,v in filtros.items() if str(v).strip()}
        for k in ('desde','hasta'):
            if k in filtros: fecha(filtros[k])
        if filtros.get('desde','0000')>filtros.get('hasta','9999'): raise ReglaError('El rango de fechas está invertido.')
        filas=self.consultar(filtros)
        totales={k:round(sum(r[k] for r in filas if r[k] is not None),2) for k in (filas[0] if filas else {}) if k.endswith('_COP') and 'por_unidad' not in k}
        return dict(titulo=self.titulo,totales=totales,filas=filas,columnas=list(filas[0]) if filas else [],cantidad=len(filas),mensaje='' if filas else 'No hay resultados para los filtros seleccionados.')
    @abstractmethod
    def consultar(self,filtros): pass
    def contexto(self,f):
        condiciones=[]; params=[]
        for key,col in [('finca','l.finca'),('lote','s.lote'),('cultivo','s.cultivo'),('siembra','s.id'),('estado','s.estado')]:
            if f.get(key): condiciones.append(col+'=?'); params.append(f[key])
        return condiciones,params
    def periodo(self,c,p,f,col):
        for k,op in [('desde','>='),('hasta','<=')]:
            if f.get(k): c.append(col+op+'?'); p.append(f[k])
    def where(self,c): return ' WHERE '+' AND '.join(c) if c else ''

class InformeSiembras(InformePlantilla):
    titulo='Siembras'
    def consultar(self,f):
        c,p=self.contexto(f); self.periodo(c,p,f,'s.fecha')
        return self.servicio.filas('SELECT s.id AS Siembra,f.nombre AS Finca,l.nombre AS Lote,c.nombre AS Cultivo,s.fecha AS Fecha,s.estimada AS Cosecha_estimada,s.area AS Area_ha,s.estado AS Estado FROM siembras s JOIN lotes l ON s.lote=l.id JOIN fincas f ON f.id=l.finca JOIN cultivos c ON c.id=s.cultivo'+self.where(c)+' ORDER BY s.fecha DESC',p)

class InformeInventario(InformePlantilla):
    titulo='Inventario y consumo'
    def consultar(self,f):
        co=[];pa=[];self.periodo(co,pa,f,'fecha')
        entradas={r['insumo']:r['n'] for r in self.servicio.filas('SELECT insumo,SUM(cantidad) n FROM compras'+self.where(co)+' GROUP BY insumo',pa)}
        if f.get('siembra'): co.append('siembra=?');pa.append(f['siembra'])
        salidas={r['insumo']:r['n'] for r in self.servicio.filas('SELECT insumo,SUM(cantidad) n FROM aplicaciones'+self.where(co)+' GROUP BY insumo',pa)}
        salida=[]
        for i in self.servicio.filas('SELECT * FROM insumos ORDER BY nombre'):
            if f.get('categoria') and i['categoria']!=f['categoria']:continue
            if f.get('siembra') and i['id'] not in salidas:continue
            salida.append(dict(Insumo=i['nombre'],Categoria=i['categoria'],Unidad=i['unidad'],Stock_actual=i['stock'],Entradas=entradas.get(i['id'],0),Consumo=salidas.get(i['id'],0),Valor_COP=i['valor']/100,Alerta='BAJO MÍNIMO' if i['stock']<=i['minimo'] else 'Normal'))
        return salida

class InformeProduccion(InformePlantilla):
    titulo='Producción'
    def consultar(self,f):
        c,p=self.contexto(f); self.periodo(c,p,f,'h.fecha')
        return self.servicio.filas('SELECT s.id AS Siembra,l.nombre AS Lote,c.nombre AS Cultivo,h.unidad AS Unidad,h.calidad AS Calidad,SUM(h.cantidad) AS Produccion,s.area AS Area_ha,ROUND(SUM(h.cantidad)/s.area,3) AS Rendimiento_por_ha FROM cosechas h JOIN siembras s ON h.siembra=s.id JOIN lotes l ON l.id=s.lote JOIN cultivos c ON c.id=s.cultivo'+self.where(c)+' GROUP BY s.id,h.unidad,h.calidad',p)

class InformeCostos(InformePlantilla):
    titulo='Costos'
    def consultar(self,f):
        c,p=self.contexto(f); self.periodo(c,p,f,'m.fecha')
        if f.get('categoria'): c.append('m.categoria=?'); p.append(f['categoria'])
        return self.servicio.filas("SELECT s.id AS Siembra,c.nombre AS Cultivo,m.categoria AS Categoria,SUM(m.valor)/100.0 AS Total_COP FROM (SELECT siembra,fecha,'Insumos' AS categoria,costo AS valor FROM aplicaciones UNION ALL SELECT siembra,fecha,categoria,valor FROM costos) m JOIN siembras s ON s.id=m.siembra JOIN lotes l ON l.id=s.lote JOIN cultivos c ON c.id=s.cultivo"+self.where(c)+' GROUP BY s.id,m.categoria',p)

class InformeRentabilidad(InformePlantilla):
    titulo='Rentabilidad'
    def consultar(self,f):
        c,p=self.contexto(f)
        siembras=self.servicio.filas('SELECT s.id,c.nombre AS cultivo,c.unidad FROM siembras s JOIN lotes l ON l.id=s.lote JOIN cultivos c ON c.id=s.cultivo'+self.where(c),p)
        co=[];pa=[];self.periodo(co,pa,f,'fecha')
        def agrupar(tabla,col):
            return {r['siembra']:r['n'] for r in self.servicio.filas(f'SELECT siembra,SUM({col}) n FROM {tabla}'+self.where(co)+' GROUP BY siembra',pa)}
        aplicados=agrupar('aplicaciones','costo');adicionales=agrupar('costos','valor');produccion=agrupar('cosechas','cantidad')
        cv=[];pv=[];self.periodo(cv,pv,f,'v.fecha')
        ingresos={r['siembra']:r['n'] for r in self.servicio.filas('SELECT h.siembra,SUM(v.total) n FROM ventas v JOIN cosechas h ON h.id=v.cosecha'+self.where(cv)+' GROUP BY h.siembra',pv)}
        salida=[]
        for s in siembras:
            ident=s['id'];costo=aplicados.get(ident,0)+adicionales.get(ident,0);ingreso=ingresos.get(ident,0);prod=produccion.get(ident,0)
            salida.append(dict(Siembra=ident,Cultivo=s['cultivo'],Unidad=s['unidad'],Produccion=prod,Ingresos_COP=ingreso/100,Costos_COP=costo/100,Utilidad_COP=(ingreso-costo)/100,Costo_por_unidad_COP=round(costo/100/prod,2) if prod else None))
        return salida

INFORMES={'siembras':InformeSiembras,'inventario':InformeInventario,'produccion':InformeProduccion,'costos':InformeCostos,'rentabilidad':InformeRentabilidad}
