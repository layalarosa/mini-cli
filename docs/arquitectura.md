# AcmeCloud: Arquitectura técnica

## Visión general

AcmeCloud se compone de tres capas principales:

1. **Cliente de escritorio** (Electron): sincroniza la carpeta local con el
   servidor mediante WebSockets.
2. **API REST** (Python/Starlette): autenticación, metadatos de archivos y
   gestión de equipos.
3. **Almacenamiento de objetos** (MinIO compatible con S3): almacena los
   contenidos binarios de los archivos.

## Base de datos

Los metadatos (usuarios, equipos, archivos, versiones) viven en PostgreSQL.
Cada archivo tiene una fila de metadatos y uno o más objetos en MinIO.

## Flujo de subida de un archivo

1. El cliente calcula el hash SHA-256 localmente.
2. La API recibe el hash y devuelve una URL de subida firmada (presigned URL).
3. El cliente sube el binario directamente a MinIO.
4. La API registra el nuevo objeto en PostgreSQL y notifica al equipo por
   WebSocket.

## Sincronización

El cliente mantiene un registro de eventos (journal). Ante un cambio local,
encola un evento `UPLOAD_CHANGED`; ante un cambio remoto recibido por
WebSocket, ejecuta un `DOWNLOAD`. Los conflictos se resuelven conservando la
versión más reciente según el timestamp del servidor.

## Autenticación

Se usa JWT con expiración de 15 minutos y refresh token de 7 días. Las
contraseñas se almacenan con bcrypt.
