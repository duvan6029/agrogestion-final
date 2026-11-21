from pathlib import Path
from core import AgroServicio
if __name__=='__main__':
    base=Path(__file__).parent/'datos'
    servicio=AgroServicio(base/'agrogestion.sqlite')
    servicio.inicializar()
    print(servicio.respaldo(base/'respaldos'))
