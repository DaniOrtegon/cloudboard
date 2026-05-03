# ☁ CloudBoard

Aplicación web de notas personales desplegada completamente en AWS con arquitectura serverless. El proyecto cubre el ciclo completo: red, base de datos, API, frontend, procesamiento asíncrono, containerización y observabilidad.

**Stack:** Lambda · API Gateway · RDS MySQL · S3 · ECR · CloudWatch · VPC

---

## Arquitectura

```
Usuario
  └── S3 (frontend estático)
        └── fetch() → API Gateway
                        └── Lambda (get / create / delete)
                              ├── RDS MySQL (subnet privada)
                              └── Lambda Processor (async)
                                    └── S3 Logs
```

**VPC cloudboard-vpc (10.0.0.0/16)**

| Subnet | CIDR | AZ | Contenido |
|---|---|---|---|
| cloudboard-subnet-public | 10.0.1.0/24 | us-east-1a | Lambda functions |
| cloudboard-subnet-private | 10.0.2.0/24 | us-east-1b | RDS MySQL |

La subnet privada no tiene ruta al Internet Gateway — aunque alguien conociera el endpoint de RDS, no hay camino de red para llegar.

---

## Servicios y decisiones de diseño

### Red — VPC + Security Groups
VPC propia con separación pública/privada. El control de acceso a RDS se define por identidad de security group (sg-api → sg-db en puerto 3306), no por IP fija. Esto permite que Lambda escale a múltiples instancias sin tocar ninguna regla de red.

### Base de datos — RDS MySQL
Instancia `db.t3.micro` en Single-AZ con acceso público desactivado. La alternativa habitual sería MySQL en EC2, pero RDS elimina la carga operativa (backups, parches, alta disponibilidad) a cambio de algo más de coste — tradeoff correcto para este proyecto.

> **Deuda técnica conocida:** en producción, las credenciales de RDS irían en AWS Secrets Manager en vez de variables de entorno de Lambda. La conexión usaría SSL habilitado (`ssl={'ca': '/rds-ca.pem'}`) en lugar del workaround actual (`ssl={'ssl': False}`) necesario en el entorno Academy.

### API — Lambda + API Gateway
Tres funciones Python 3.11 con un layer compartido de `pymysql` + `cryptography`. API Gateway REST con Lambda Proxy Integration habilitado y CORS configurado por recurso.

| Función | Método | Ruta |
|---|---|---|
| cloudboard-get-notes | GET | /notes |
| cloudboard-create-note | POST | /notes |
| cloudboard-delete-note | DELETE | /notes/{id} |

API URL: `https://fe9ow6g3xf.execute-api.us-east-1.amazonaws.com/prod`

### Frontend — S3 Static Website Hosting
Bucket público con Static Website Hosting. En producción la arquitectura correcta es S3 + CloudFront con OAC (bucket privado, HTTPS automático, distribución global) — no disponible en AWS Academy.

### Procesamiento asíncrono — Event-driven
`cloudboard-create-note` invoca al processor con `InvocationType='Event'` (fire and forget) y devuelve la respuesta inmediatamente. El processor se ejecuta de forma independiente y escribe un log JSON en S3. El processor vive **fuera de la VPC** porque S3 es un servicio público de AWS — dentro de la VPC sin NAT Gateway no tiene salida a internet.

Este patrón (una acción dispara reacciones independientes en paralelo) es el mismo que usa un e-commerce cuando una compra genera simultáneamente el email de confirmación, la actualización de inventario y la factura.

### Contenedores — Docker + ECR
Imagen construida con **multi-stage build**: primera etapa instala dependencias, segunda etapa copia solo los paquetes compilados sobre una imagen limpia. Resultado: ~48 MB frente a los 200+ MB de una build convencional.

Tras publicar la imagen en ECR se ejecutó un escaneo de vulnerabilidades que detectó dos CVEs en `glibc` (HIGH y MEDIUM) provenientes de la imagen base `python:3.11-slim`. La corrección es actualizar a una versión de imagen base con `glibc` parcheado.

### Observabilidad — CloudWatch
Logs automáticos de cada invocación Lambda (INIT_START, START, END, REPORT con duración y memoria). Dashboard con métricas de Invocations, Errors, Duration y Throttles en `cloudboard-get-notes`.

---

## Problemas encontrados durante el despliegue

Estos son los errores reales que aparecieron y cómo se resolvieron:

**sg-api sin regla de egress al puerto 3306**
Lambda recibía peticiones pero no alcanzaba RDS. sg-api solo tenía salida por el puerto 443. Solución:
```bash
aws ec2 authorize-security-group-egress \
  --group-id sg-0c35ce0a04fac06cd \
  --protocol tcp --port 3306 \
  --source-group sg-055c651604299c69c
```

**MySQL 8.4 requiere el paquete `cryptography`**
El layer inicial solo incluía `pymysql`. Lambda fallaba con `cryptography package is required for caching_sha2_password`. Solución: recrear el layer incluyendo `cryptography` y añadir `ssl={'ssl': False}` a todas las conexiones.

**RDS desplegado en us-east-1a (subnet pública)**
El subnet group incluía ambas subnets y RDS eligió us-east-1a (la pública). Lambda estaba solo en us-east-1b y no alcanzaba RDS. Solución: conectar Lambda a ambas subnets para cubrir las dos AZs. En producción, el subnet group de RDS debería incluir exclusivamente subnets privadas.

**Lambda Proxy Integration desactivado**
API Gateway no pasaba el body del POST ni el `{id}` del DELETE a Lambda. Las notas se creaban sin título ni contenido; el DELETE devolvía siempre "ID requerido". Solución: activar Lambda Proxy Integration en los tres métodos y redesplegar.

**cloudboard-note-processor daba timeout dentro de la VPC**
El processor estaba en la VPC pero S3 es un servicio público. Sin NAT Gateway, Lambda dentro de la VPC no tiene salida a internet para alcanzar S3. Solución: quitar la función de la VPC completamente.

**CORS bloqueaba el frontend**
El navegador bloqueaba las peticiones desde S3 hacia la API. Solución: habilitar CORS en API Gateway para los recursos `/notes` (GET, POST) y `/notes/{id}` (DELETE) con `Access-Control-Allow-Origin: *`.

---

## Estructura del repositorio

```
cloudboard/
├── lambda/
│   ├── get_notes/lambda_function.py
│   ├── create_note/lambda_function.py
│   ├── delete_note/lambda_function.py
│   └── processor/lambda_function.py
├── frontend/
│   └── index.html
└── docker/
    ├── Dockerfile
    ├── app.py
    └── requirements.txt
```

---

## Entorno

Desplegado en **AWS Academy** — cuenta real con créditos limitados y algunas restricciones respecto a una cuenta estándar: sin acceso a CloudFront y sin posibilidad de crear roles IAM personalizados. Las funciones Lambda usan `LabRole`, un rol predefinido con permisos amplios. En producción cada función tendría su propio rol con únicamente los permisos necesarios (principio de mínimo privilegio).

El acceso funciona mediante credenciales temporales gestionadas por STS — el mismo mecanismo que usa AWS en producción cuando un servicio necesita asumir un rol.

---

## Próximos pasos

- Infraestructura como código con Terraform o AWS CloudFormation
- Secrets Manager para las credenciales de RDS
- CloudFront delante de S3 con OAC
- CloudWatch Alarms sobre error rate de Lambda (SNS → email)
- SSL habilitado en las conexiones pymysql
