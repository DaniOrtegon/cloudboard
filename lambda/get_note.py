import json, os
import pymysql

def lambda_handler(event, context):
    conn = pymysql.connect(
        host=os.environ['DB_HOST'], user=os.environ['DB_USER'],
        password=os.environ['DB_PASS'], db=os.environ['DB_NAME'],
        cursorclass=pymysql.cursors.DictCursor, ssl={'ssl': False}
    )
    with conn.cursor() as cursor:
        cursor.execute('SELECT * FROM notes ORDER BY created_at DESC')
        notes = cursor.fetchall()
    conn.close()
    return {
        'statusCode': 200,
        'headers': {'Access-Control-Allow-Origin': '*'},
        'body': json.dumps(notes, default=str)
    }
