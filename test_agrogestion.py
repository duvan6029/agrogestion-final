"""Pruebas de reglas del SRS, patrones y autorización HTTP. No usa la base real."""
import unittest
import tempfile
import io
import sqlite3
from datetime import date
from pathlib import Path
from core import *
from app import create_app
from semilla import cargar

class AgroTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.app=create_app(Path(self.tmp.name)/'test.sqlite',testing=True)
        self.s=self.app.servicio; cargar(self.s)
        self.hoy=date.today().isoformat(); self.client=self.app.test_client()
    def post(self,url,data):
        self.client.get('/login')
        with self.client.session_transaction() as sess: token=sess['csrf']
        return self.client.post(url,data={**data,'csrf':token},follow_redirects=True)
    def login(self,nombre='admin'):
        return self.post('/login',dict(nombre=nombre,clave='Agro2026!'))
    def test_demo_promedio_ponderado(self):
        ins=self.s.filas('SELECT * FROM insumos WHERE id=1')[0]
        self.assertEqual(ins['stock'],20); self.assertEqual(ins['valor'],6000000)
        self.assertEqual(self.s.filas('SELECT costo FROM aplicaciones')[0]['costo'],54000000)
    def test_utilidad_y_costo_por_unidad(self):
        r=InformeRentabilidad(self.s).generar({})['filas'][0]
        self.assertEqual(r['Ingresos_COP'],1200000); self.assertEqual(r['Costos_COP'],640000)
        self.assertEqual(r['Utilidad_COP'],560000); self.assertEqual(r['Costo_por_unidad_COP'],426.67)
    def test_lote_ocupado(self):
        with self.assertRaises(ReglaError): self.s.registrar('siembras',dict(lote=1,cultivo=1,fecha=self.hoy,area=1,semilla=1,responsable='Ana'),'admin')
    def test_lote_nombre_duplicado(self):
        with self.assertRaises(sqlite3.IntegrityError): self.s.guardar('lotes',dict(finca=1,nombre='Lote Norte',ubicacion='X',area=1,suelo='Franco'),'admin')
    def test_area_excesiva(self):
        with self.assertRaises(ReglaError): self.s.registrar('siembras',dict(lote=2,cultivo=1,fecha=self.hoy,area=5,semilla=1,responsable='Ana'),'admin')
    def test_cultivo_inactivo(self):
        self.s.desactivar('cultivos',2,'admin')
        with self.assertRaises(ReglaError): self.s.registrar('siembras',dict(lote=2,cultivo=2,fecha=self.hoy,area=1,semilla=1,responsable='Ana'),'admin')
    def test_fecha_estimada(self):
        r=self.s.filas('SELECT * FROM siembras')[0]
        self.assertEqual((fecha(r['estimada'])-fecha(r['fecha'])).days,120)
    def test_insuficiente_rollback(self):
        with self.assertRaises(ReglaError): self.s.registrar('aplicaciones',dict(siembra=1,insumo=1,fecha=self.hoy,cantidad=21,responsable='Ana'),'admin')
        self.assertEqual(self.s.filas('SELECT stock FROM insumos WHERE id=1')[0]['stock'],20)
        self.assertEqual(len(self.s.filas('SELECT * FROM aplicaciones')),1)
    def test_agotar_stock_sin_residuo(self):
        self.s.registrar('aplicaciones',dict(siembra=1,insumo=1,fecha=self.hoy,cantidad=20,responsable='Ana'),'admin')
        i=self.s.filas('SELECT * FROM insumos WHERE id=1')[0]
        self.assertEqual(i['stock'],0);self.assertEqual(i['valor'],0)
    def test_observer_alerta_resuelta_por_compra(self):
        self.assertTrue(self.s.filas('SELECT * FROM alertas WHERE insumo=1'))
        self.s.registrar('compras',dict(insumo=1,proveedor=1,fecha=self.hoy,cantidad=100,unitario=3000),'admin')
        self.assertFalse(self.s.filas('SELECT * FROM alertas WHERE insumo=1'))
    def test_suscribir_y_retirar(self):
        class Prueba(Observador):
            def __init__(self): self.n=0
            def actualizar(self,e,db): self.n+=1
        obs=Prueba(); sujeto=EventosInventario(); sujeto.suscribir(obs); sujeto.notificar({},None)
        sujeto.retirar(obs);sujeto.notificar({},None);self.assertEqual(obs.n,1)
    def test_estado_final_bloquea_aplicacion(self):
        self.s.estado(1,'Cosechada','Ciclo terminado','admin')
        with self.assertRaises(ReglaError): self.s.registrar('aplicaciones',dict(siembra=1,insumo=1,fecha=self.hoy,cantidad=1,responsable='Ana'),'admin')
    def test_estado_final_no_reabre(self):
        self.s.estado(1,'Perdida','Inundación','admin')
        with self.assertRaises(ReglaError): self.s.estado(1,'Cosechada','Cambiar','admin')
    def test_ventas_excesivas(self):
        with self.assertRaises(ReglaError): self.s.registrar('ventas',dict(cosecha=1,fecha=self.hoy,cantidad=501,unitario=1000,comprador='Ana'),'admin')
    def test_cosechas_parciales(self):
        self.s.registrar('cosechas',dict(siembra=1,fecha=self.hoy,cantidad=500,calidad='Segunda'),'admin')
        self.assertEqual(sum(r['Produccion'] for r in InformeProduccion(self.s).generar({})['filas']),2000)
    def test_historico_conservado(self):
        self.s.desactivar('cultivos',1,'admin');self.assertEqual(len(InformeSiembras(self.s).generar({})['filas']),1)
    def test_password_hash_y_sal(self):
        a=hash_clave('password');b=hash_clave('password')
        self.assertNotEqual(a,b);self.assertTrue(verificar('password',a));self.assertFalse(verificar('otro',a))
    def test_rol_consultor_no_modifica(self):
        self.login('consultor');self.assertEqual(self.client.get('/maestros/fincas').status_code,403)
        self.assertEqual(self.post('/movimientos/costos',dict(fecha=self.hoy)).status_code,403)
    def test_operario_no_admin(self):
        self.login('operario');self.assertEqual(self.client.get('/maestros/usuarios').status_code,403)
        self.assertEqual(self.client.get('/informes/costos').status_code,403)
    def test_expira_sesion(self):
        self.login()
        with self.client.session_transaction() as sess:sess['ultima']=0
        self.assertEqual(self.client.get('/').status_code,302)
    def test_csrf(self):
        self.assertEqual(self.client.post('/login',data={'nombre':'admin'}).status_code,400)
    def test_paginas_admin(self):
        self.login()
        for url in ['/']+['/maestros/'+x for x in MAESTROS]+['/movimientos/'+x for x in ['siembras','compras','aplicaciones','cosechas','ventas','costos']]+['/informes/'+x for x in INFORMES]:
            with self.subTest(url=url):self.assertEqual(self.client.get(url).status_code,200)
    def test_template_method_abstracto(self):
        with self.assertRaises(TypeError): InformePlantilla(self.s)
    def test_filtro_siembra(self):
        for tipo in ['siembras','produccion','costos','rentabilidad']:
            self.assertEqual(INFORMES[tipo](self.s).generar({'siembra':'999'})['cantidad'],0)
    def test_rango_invertido(self):
        with self.assertRaises(ReglaError): InformeSiembras(self.s).generar({'desde':'2026-12-31','hasta':'2026-01-01'})
    def test_pdf_y_excel(self):
        from openpyxl import load_workbook
        self.login()
        for tipo in INFORMES:
            pdf=self.client.get('/informes/'+tipo+'?formato=pdf');self.assertEqual(pdf.status_code,200);self.assertTrue(pdf.data.startswith(b'%PDF'))
            x=self.client.get('/informes/'+tipo+'?formato=xlsx');self.assertEqual(x.status_code,200)
            wb=load_workbook(io.BytesIO(x.data)); self.assertGreater(wb.active.max_row,2)
    def test_respaldo(self):
        ruta=self.s.respaldo(Path(self.tmp.name)/'backups')
        with sqlite3.connect(ruta,factory=Conexion) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM usuarios').fetchone()[0],3)
    def test_ultimo_administrador(self):
        with self.assertRaises(ReglaError):self.s.guardar('usuarios',dict(nombre='admin',email='admin@agro.local',rol='Consultor',clave=''),'admin',1)
    def test_auditoria_creador(self):
        r=self.s.filas('SELECT * FROM fincas')[0]
        self.assertEqual(r['creador'],'Configuración inicial');self.assertTrue(r['creado'])
    def test_numero_no_finito(self):
        for n in ['NaN','Infinity','-1']:
            with self.assertRaises(ReglaError):numero(n)

if __name__=='__main__':unittest.main(verbosity=2)
