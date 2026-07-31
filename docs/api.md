# AcmeCloud: Referencia de la API REST

Base URL: `https://api.acmecloud.example.com/v1`

Autenticación: cabecera `Authorization: Bearer <token>`.

## Crear un archivo (metadata)

`POST /v1/files`

Cuerpo (JSON):

```json
{
  "team_id": "team_123",
  "name": "informe-q2.pdf",
  "mime_type": "application/pdf",
  "size": 204800,
  "sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
}
```

Respuesta `201`:

```json
{
  "file_id": "file_456",
  "upload_url": "https://s3.acmecloud.example.com/files/...",
  "upload_method": "PUT"
}
```

## Subir el binario

`PUT <upload_url>` con el cuerpo binario del archivo. No requiere autenticación
adicional porque la URL está firmada.

## Listar archivos de un equipo

`GET /v1/files?team_id=team_123&limit=50`

Devuelve una lista de archivos ordenados por fecha de modificación descendente.

## Compartir un archivo

`POST /v1/files/{file_id}/shares`

```json
{
  "permission": "read",
  "expires_in_days": 7
}
```

Devuelve `{"share_url": "https://acmecloud.example.com/s/abc123"}`.

## Errores

- `400 Bad Request`: JSON inválido o parámetros faltantes.
- `401 Unauthorized`: token ausente o vencido.
- `404 Not Found`: recurso inexistente.
- `429 Too Many Requests`: límite de tasa excedido (100 req/min por usuario).
