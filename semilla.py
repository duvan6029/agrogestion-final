"""Carga demostrativa idempotente: nunca borra datos existentes."""
from datetime import date,timedelta
from pathlib import Path
from core import AgroServicio

def cargar(servicio):
    if servicio.filas('SELECT id FROM usuarios'): return False
    s=servicio; autor='Configuración inicial'
    for nombre,rol in [('admin','Administrador'),('operario','Operario'),('consultor','Consultor')]:
        s.guardar('usuarios',dict(nombre=nombre,email=nombre+'@agro.local',rol=rol,clave='Agro2026!'),autor)
    finca=s.guardar('fincas',dict(nombre='Finca El Porvenir',ubicacion='Cereté, Córdoba',area='20',suelo='Franco arcilloso'),autor)
    lote=s.guardar('lotes',dict(finca=finca,nombre='Lote Norte',ubicacion='Sector norte',area='5',suelo='Franco'),autor)
    s.guardar('lotes',dict(finca=finca,nombre='Lote Sur',ubicacion='Sector sur',area='4',suelo='Franco'),autor)
    cultivo=s.guardar('cultivos',dict(nombre='Maíz',variedad='Amarillo',ciclo='120',unidad='kg'),autor)
    s.guardar('cultivos',dict(nombre='Yuca',variedad='Regional',ciclo='240',unidad='kg'),autor)
    proveedor=s.guardar('proveedores',dict(nombre='Agroinsumos del Sinú',contacto='3001234567'),autor)
    ins=s.guardar('insumos',dict(nombre='Fertilizante NPK',categoria='Fertilizante',unidad='kg',minimo='25'),autor)
    s.guardar('insumos',dict(nombre='Semilla de maíz',categoria='Semillas',unidad='kg',minimo='10'),autor)
    hoy=date.today(); fecha=lambda dias:(hoy-timedelta(days=dias)).isoformat()
    siembra=s.registrar('siembras',dict(lote=lote,cultivo=cultivo,fecha=fecha(120),area='2',semilla='40',responsable='Duván Taboada'),autor)
    s.registrar('compras',dict(insumo=ins,proveedor=proveedor,fecha=fecha(115),cantidad='100',unitario='2000'),autor)
    s.registrar('compras',dict(insumo=ins,proveedor=proveedor,fecha=fecha(110),cantidad='100',unitario='4000'),autor)
    s.registrar('aplicaciones',dict(siembra=siembra,insumo=ins,fecha=fecha(90),cantidad='180',responsable='Emiliano Martínez'),autor)
    s.registrar('costos',dict(siembra=siembra,fecha=fecha(80),categoria='Mano de obra',concepto='Preparación del terreno',valor='100000'),autor)
    cosecha=s.registrar('cosechas',dict(siembra=siembra,fecha=fecha(2),cantidad='1500',calidad='Primera'),autor)
    s.registrar('ventas',dict(cosecha=cosecha,fecha=fecha(1),comprador='Cooperativa del Sinú',cantidad='1000',unitario='1200'),autor)
    return True

if __name__=='__main__':
    s=AgroServicio(Path(__file__).parent/'datos/agrogestion.sqlite');s.inicializar()
    print('Datos de demostración cargados.' if cargar(s) else 'La base ya tiene usuarios. Se conservaron los datos existentes.')
