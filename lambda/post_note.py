import json, os, uuid
import pymysql, boto3

def lambda_handler(event, context):
    body = json.loads(event.get('body') or '{}')
    note_id = str(uuid.uuid4())
    conn = pymysql.connect(
        host=os.environ['DB_HOST'], user=os.environ['DB_USER'],
        password=os.environ['DB_PASS'], db=os.environ['DB_NAME'],
        ssl={'ssl': False}
    )
    with conn.cursor() as cursor:
        cursor.execute(
            'INSERT INTO notes (id, title, content) VALUES (%s, %s, %s)',
            (note_id, body.get('title',''), body.get('content',''))
        )
    conn.commit()
    conn.close()
    boto3.client('lambda').invoke(
        FunctionName='cloudboard-note-processor',
        InvocationType='Event',
        Payload=json.dumps({'note_id': note_id})
    )
    return {
        'statusCode': 201,
        'headers': {'Access-Control-Allow-Origin': '*'},
        'body': json.dumps({'id': note_id, 'message': 'Nota creada'})
    }
