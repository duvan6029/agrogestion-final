"""Medición local reproducible con 10.000 registros, sin alterar la base del usuario."""
import tempfile
from pathlib import Path
from time import perf_counter
from core import AgroServicio,INFORMES
from semilla import cargar

def medir():
    with tempfile.TemporaryDirectory() as temp:
        s=AgroServicio(Path(temp)/'carga.sqlite');s.inicializar();cargar(s)
        with s.conectar() as db:
            db.executemany("INSERT INTO siembras(lote,cultivo,fecha,area,semilla,responsable,estimada,estado) VALUES (2,1,'2025-01-01',1,10,'Prueba','2025-05-01','Cosechada')",[()]*10000)
            ids=[r[0] for r in db.execute('SELECT id FROM siembras WHERE id>1')]
            db.executemany("INSERT INTO cosechas(siembra,fecha,cantidad,unidad,calidad) VALUES (?,'2025-05-01',100,'kg','Primera')",[(i,) for i in ids])
            db.executemany("INSERT INTO costos(siembra,fecha,categoria,concepto,valor) VALUES (?,'2025-01-01','Otros','Carga sintética',10000)",[(i,) for i in ids])
            db.executemany("INSERT INTO insumos(nombre,categoria,unidad,minimo) VALUES (?,'Prueba','kg',1)",[(f'Insumo de carga {i}',) for i in ids])
        for nombre,clase in INFORMES.items():
            inicio=perf_counter();r=clase(s).generar({});segundos=perf_counter()-inicio
            print(f'{nombre}: {r["cantidad"]} filas en {segundos:.3f} s')
            if segundos>=5:raise AssertionError('La consulta superó 5 segundos en este equipo.')
if __name__=='__main__':medir()
