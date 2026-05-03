import json, os
import pymysql

def lambda_handler(event, context):
    note_id = (event.get('pathParameters') or {}).get('id')
    if not note_id:
        return {'statusCode': 400,
                'headers': {'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'ID requerido'})}
    conn = pymysql.connect(
        host=os.environ['DB_HOST'], user=os.environ['DB_USER'],
        password=os.environ['DB_PASS'], db=os.environ['DB_NAME'],
        ssl={'ssl': False}
    )
    with conn.cursor() as cursor:
        cursor.execute('DELETE FROM notes WHERE id = %s', (note_id,))
    conn.commit()
    conn.close()
    return {
        'statusCode': 200,
        'headers': {'Access-Control-Allow-Origin': '*'},
        'body': json.dumps({'message': 'Nota eliminada'})
    }
