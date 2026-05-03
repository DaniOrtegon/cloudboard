import json, boto3, os
from datetime import datetime

def lambda_handler(event, context):
    s3 = boto3.client('s3')
    note_id = event.get('note_id', 'unknown')
    log = {
        'timestamp': datetime.utcnow().isoformat(),
        'action': 'note_created',
        'note_id': note_id,
        'processed': True
    }
    s3.put_object(
        Bucket=os.environ['LOG_BUCKET'],
        Key=f'logs/{note_id}.json',
        Body=json.dumps(log),
        ContentType='application/json'
    )
    print(f'Log guardado para nota {note_id}')
    return {'status': 'ok'}
