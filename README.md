# Rifas Entre Amigos del Rancho — MVP

## Qué incluye
- Base de datos SQLite local (`rifas.db`)
- Rifa de prueba con 10,000 números
- Selector de números disponibles, apartados y vendidos
- Validación en servidor para evitar apartar números que ya no están disponibles
- Formulario de participante
- Panel administrativo básico para crear nuevas rifas

## Ejecutar en computadora
1. Instala Python 3.10 o superior.
2. Abre una terminal dentro de esta carpeta.
3. Ejecuta:
   `python -m venv .venv`
4. Activa el entorno virtual:
   - Windows: `.venv\Scripts\activate`
   - macOS/Linux: `source .venv/bin/activate`
5. Instala dependencias:
   `pip install -r requirements.txt`
6. Inicia:
   `python app.py`
7. Abre en el navegador:
   `http://127.0.0.1:5000`

## Importante
Este es un MVP de desarrollo. Antes de vender boletos reales hay que agregar autenticación segura, control de roles, pagos, webhooks de pago, expiración automática de apartados, auditoría, backups, seguridad de producción y revisar los requisitos legales aplicables al tipo de sorteo.
