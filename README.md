# AgroGestión

Proyecto final de Programación III — Duván Taboada y Emiliano Martínez. Docente: Pierre Peña.

Aplicación web local para gestionar fincas, lotes, cultivos, inventario, ciclos productivos y resultados económicos según SRS_AgroGestion.docx. Los patrones de diseño reales son **Observer y Template Method**; las etiquetas CRUD/informes del SRS describen familias de requerimientos, no patrones GoF.

## Inicio en Windows

1. Extraer todo el ZIP en una carpeta propia.
2. Instalar Python 3.11 o superior (activar «Add Python to PATH»).
3. Abrir `iniciar.cmd` con doble clic. La primera vez necesita Internet.
4. Abrir http://127.0.0.1:5000 si el navegador no se abre automáticamente.
5. Dejar abierta la terminal mientras se usa la aplicación. Ctrl+C detiene el servidor.

También se puede iniciar desde PowerShell dentro de esta carpeta:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe semilla.py
.\.venv\Scripts\python.exe app.py
```

No se necesita activar el entorno virtual ni modificar las políticas de PowerShell.

## Cuentas de demostración

| Usuario | Contraseña | Rol |
| --- | --- | --- |
| admin | Agro2026! | Administrador |
| operario | Agro2026! | Operario |
| consultor | Agro2026! | Consultor |

Son cuentas de demostración. Antes de usar datos reales, cambiar las contraseñas desde Usuarios. La carga inicial es idempotente: si existen usuarios no borra ni reinicia la base. Las fechas de ejemplo se ajustan al día de instalación.

## Funciones

- CRUD de fincas, lotes, cultivos, proveedores, insumos y usuarios con desactivación e historial.
- Siembras con fecha estimada, control de área y una sola siembra activa por lote.
- Compras con costo promedio ponderado del inventario.
- Aplicaciones con descuento atómico de stock y asignación del costo a la siembra.
- Cosechas parciales, ventas limitadas a la producción disponible y costos por categoría.
- Cierre de siembra cosechada/perdida con observación; no se reabre el ciclo ni se permiten aplicaciones posteriores.
- Cinco informes con filtros y exportación PDF/Excel nativo (.xlsx).
- Usuarios y permisos comprobados en servidor. Consultor: panel e informes; operario: siembras, aplicaciones, cosechas y costos; administrador: todas las funciones.
- Sesión con cierre tras 15 minutos de inactividad, CSRF, hash PBKDF2 con sal por contraseña y auditoría.
- Copia SQLite diaria al primer acceso de cada día y descarga manual desde el panel del administrador.

Las operaciones transaccionales se agregan, no se editan ni eliminan: así se conserva la trazabilidad de stock y costos. Los catálogos se desactivan sin borrar claves relacionadas. Las alertas iniciales incluyen insumos con stock cero.

## Arquitectura y patrones

- `app.py`: presentación Flask, rutas, autenticación, autorización y exportadores.
- `core.py`: reglas, persistencia SQLite y los dos patrones.
- `templates/` y `static/`: interfaz HTML/CSS responsiva, sin servicios externos.
- `semilla.py`: escenario demostrativo.
- `test_agrogestion.py`: pruebas automatizadas con bases temporales independientes.
- `GUIA_SUSTENTACION.html`: guion de demostración, preguntas y diagrama UML.
- `docs/patrones.puml`: UML editable.

### Observer

Sujeto `EventosInventario`; contrato abstracto `Observador`; observadores `AlertaStock` y `AuditorInventario`. El servicio publica el evento al registrar compras y aplicaciones. Cada observador procesa la misma notificación sin que el sujeto conozca su lógica. `suscribir()` y `retirar()` permiten cambios dinámicos. Alertas y stock se confirman en la misma transacción; una excepción revierte la operación completa.

### Template Method

`InformePlantilla.generar()` fija el algoritmo: limpiar filtros, validar fechas, invocar `consultar()`, resumir importes y preparar columnas/mensaje. Las cinco clases concretas redefinen `consultar()`. Las rutas utilizan el mismo método `generar()` para cualquier informe. Se puede añadir otro informe sin duplicar el algoritmo común; basta crear la subclase y registrarla en `INFORMES`.

## Comprobación de los datos de ejemplo

Dos compras de fertilizante: 100 kg a COP 2.000 y 100 kg a COP 4.000. Promedio: COP 3.000/kg. Aplicar 180 kg cuesta COP 540.000 y deja 20 kg valorados en COP 60.000. Con mínimo de 25 kg aparece una alerta. Mano de obra: COP 100.000. Costos totales: COP 640.000. Cosecha: 1.500 kg en 2 ha, rendimiento 750 kg/ha. Venta: 1.000 kg a COP 1.200, ingresos COP 1.200.000. Utilidad: COP 560.000. Costo por unidad producida: COP 426,67/kg. Quedan 500 kg disponibles para vender.

En inventario, stock y valor son actuales; entradas y consumo corresponden al periodo filtrado. El filtro por siembra afecta al consumo, porque las compras abastecen el inventario general. Los informes de rentabilidad por periodo muestran flujos registrados en ese periodo; sin fechas muestran el ciclo completo. No se suman kg, litros y bultos entre sí. La utilidad representa ingresos registrados menos costos registrados; no es un cálculo de valoración contable de la cosecha no vendida. Los precios se almacenan en centavos COP y el redondeo es HALF_UP. Las cantidades y áreas se almacenan como números reales SQLite.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

Las pruebas cubren costo promedio, límites de stock y ventas, ciclo cerrado, áreas, duplicados, historial, hash, roles, CSRF, sesión vencida, Observer, Template Method, generación PDF/XLSX y respaldo restaurable. No afectan los datos del usuario.

## Alcance y despliegue

El servidor incluido escucha solamente en 127.0.0.1 para demostración local. SQLite es una base relacional persistente de bajo costo; el SRS menciona MySQL/PostgreSQL como ejemplos, no como requisito excluyente. Un despliegue multiusuario requiere servidor WSGI, HTTPS con certificado, política de respaldos fuera del equipo y supervisión. Configurar AGRO_HTTPS=1 solo detrás de HTTPS para activar cookies Secure. AGRO_SECRET permite inyectar una clave de sesión externa.

El 95 % de disponibilidad no puede garantizarse con un programa local; depende de la infraestructura. La copia diaria automática requiere que la aplicación reciba al menos una solicitud ese día; puede programarse una tarea de Windows para llamar a `respaldo_diario.py` sin abrir el navegador. Los respaldos contienen información sensible y deben protegerse como la base original. La aplicación no incluye facturación electrónica, nómina, sensores IoT ni predicción climática.

## Entrega y sustentación

El ejemplo del profesor pide código en GitHub, UML y programa funcionando. Repositorio del grupo: https://github.com/duvan6029/agrogestion-final . El código fuente se publica en la rama main. El ZIP contiene el código completo, la guía y el UML. Abra la guía HTML para el guion de sustentación y use el navegador para imprimirla si necesita papel.
