# Correspondencia con el SRS

| Requisito | Función implementada | Evidencia |
| --- | --- | --- |
| RF-01 | Fincas y lotes: alta, consulta, modificación y desactivación; nombre de lote único por finca | Catálogos y prueba de duplicados |
| RF-02 | Cultivos con variedad, ciclo y unidad; inactivos conservados en informes | Cultivos y prueba de histórico |
| RF-03 | Siembra con estimación de cosecha, validación de área y lote ocupado | Siembras y pruebas de área/lote/fecha |
| RF-04 | Cierre cosechada/perdida con observación y bloqueo de aplicaciones | Cerrar ciclo y prueba de estado final |
| RF-05 | Insumos y proveedores con campos obligatorios y desactivación | Catálogos |
| RF-06 | Compra con cantidad, precio y proveedor; entrada a stock | Compras, costo promedio en prueba demostrativa |
| RF-07 | Aplicación a siembra y costo promedio, actualización atómica | Aplicaciones y prueba de rollback |
| RF-08 | Alerta al alcanzar mínimo, actualización por Observer | Panel y prueba de alerta resuelta |
| RF-09 | Cosechas parciales y calidad | Cosechas y prueba de producción acumulada |
| RF-10 | Venta limitada por disponibilidad de cada cosecha | Ventas y prueba de exceso |
| RF-11 | Costos con fecha, categoría, concepto y siembra | Costos adicionales |
| RF-12 | Suma de aplicaciones y costos; costo por unidad producida | Rentabilidad y prueba de cálculo manual |
| RF-13 | Informe de siembras con filtros y PDF/XLSX | Informes, prueba de exportación |
| RF-14 | Stock actual, valor, entradas y consumo por periodo; categoría y siembra | Inventario y consumo |
| RF-15 | Producción por cultivo/lote/periodo, calidad y rendimiento | Producción |
| RF-16 | Costos por siembra/cultivo/categoría/periodo y totales | Costos |
| RF-17 | Ingresos, costos y utilidad por ciclo/cultivo/periodo | Rentabilidad |
| RF-18 | Autenticación y autorización de rutas por rol | Pruebas de rol y sesión |
| RF-19 | Gestión de usuarios, nombres/correos únicos, desactivación | Usuarios y prueba de último administrador |

Los patrones de diseño del proyecto son Observer (RF-08 y auditoría de movimientos) y Template Method (RF-13 a RF-17). Los rótulos P1/P2 del SRS son plantillas funcionales y no sustituyen estos patrones.

## Requerimientos no funcionales

RNF-01/06: interfaz española y responsiva; validada en navegador a 1440 y 390 px. No se ha realizado un estudio de usabilidad con usuarios nuevos para afirmar el objetivo de cinco minutos.

RNF-02: se incluye `verificar_rendimiento.py`, que genera una base temporal con 10.000 ciclos, cosechas, costos e insumos y mide los cinco informes. El resultado es dependiente del equipo y no garantiza el tiempo de exportación ni de una futura instalación.

RNF-03: hash PBKDF2 con sal aleatoria y sesión inactiva de 15 minutos, verificados automáticamente. El servidor local no debe exponerse a Internet directamente.

RNF-04: borrado lógico en catálogos, claves foráneas y conservación de movimientos; no hay eliminación física desde la interfaz.

RNF-05: disponibilidad del 95 % depende del hosting y de su supervisión; no se atribuye a esta demostración local.

RNF-07: presentación en app.py/templates/static, lógica y datos en core.py, clases documentadas y pruebas independientes. En una evolución de mayor escala conviene separar físicamente repositorios y servicios en más módulos.

RNF-08: copia al primer acceso diario y botón de descarga. `respaldo_diario.py` permite programar una copia con el Programador de tareas de Windows aun cuando nadie abra el navegador. No se instala una tarea en el sistema sin conocer el horario y destino de respaldo del grupo.

RNF-09: usuario y fecha de creación y modificación, más eventos de auditoría. Los movimientos de inventario también notifican al observador de auditoría.

HTTPS: pendiente del despliegue con certificado y servidor de producción. El proyecto se inicia en localhost con HTTP para demostración. SQLite es la base relacional local elegida; MySQL y PostgreSQL aparecen como ejemplos en el SRS.
