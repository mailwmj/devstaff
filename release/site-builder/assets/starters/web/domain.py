"""Pure validation; money is integer minor units, never binary float arithmetic."""
import csv
import hashlib
import io
import json
from datetime import date
from decimal import Decimal,InvalidOperation


def minor_units(value):
    if isinstance(value,bool): raise ValueError('amount must be a decimal')
    try: amount=Decimal(str(value))
    except InvalidOperation as exc: raise ValueError('amount must be a decimal') from exc
    if not amount.is_finite() or not 0<=amount<=Decimal('1000000000'): raise ValueError('amount must be finite and nonnegative')
    cents=amount*100
    if cents!=cents.to_integral_value(): raise ValueError('amount supports at most two decimal places')
    return int(cents)


def normalize_record(value):
    if not isinstance(value,dict): raise ValueError('record must be an object')
    title=value.get('title')
    if not isinstance(title,str) or not 1<=len(title.strip())<=160: raise ValueError('title must contain 1 to 160 characters')
    due=value.get('date','')
    if not isinstance(due,str): raise ValueError('date must be a string')
    if due:
        try:
            if date.fromisoformat(due).isoformat()!=due: raise ValueError()
        except ValueError as exc: raise ValueError('date must be YYYY-MM-DD') from exc
    status=value.get('status','open')
    if status not in ('open','done'): raise ValueError('status must be open or done')
    notes=value.get('notes','')
    if not isinstance(notes,str) or len(notes)>2000: raise ValueError('notes must be at most 2000 characters')
    if 'amount' in value: cents=minor_units(value['amount'])
    else:
        cents=value.get('amount_minor',0)
        if type(cents) is not int or not 0<=cents<=100000000000: raise ValueError('amount_minor must be nonnegative integer minor units')
    return {'title':title.strip(),'amount_minor':cents,'date':due,'status':status,'notes':notes}


def digest_record(record):
    return hashlib.sha256(json.dumps(record,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def import_preview(text,format_name,mapping=None):
    if not isinstance(text,str) or len(text.encode())>2000000: raise ValueError('import must be text under 2 MB')
    if format_name=='json':
        payload=json.loads(text)
        if not isinstance(payload,dict) or payload.get('schema_version')!=1 or not isinstance(payload.get('records'),list):
            raise ValueError('expected schema_version:1 export with records')
        rows=payload['records']
    elif format_name=='csv':
        mapping=mapping or {'title':'title','amount':'amount','date':'date','status':'status','notes':'notes'}
        if not isinstance(mapping,dict) or not mapping.get('title') or any(not isinstance(k,str) or not isinstance(v,str) for k,v in mapping.items()):
            raise ValueError('CSV mapping requires string column names and title')
        reader=csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
        fields=reader.fieldnames or []
        if mapping['title'] not in fields or len(fields)!=len(set(fields)): raise ValueError('CSV title missing or headers duplicated')
        rows=[]
        for row in reader:
            if len(rows)>=5000: raise ValueError('at most 5000 rows per import')
            if None in row: raise ValueError('CSV row has extra cells')
            rows.append({key:row.get(column,'') for key,column in mapping.items() if column in fields})
    else: raise ValueError('format must be json or csv')
    if len(rows)>5000: raise ValueError('at most 5000 rows per import')
    records,errors,seen=[],[],set()
    for index,value in enumerate(rows,1):
        try:
            normalized=normalize_record(value)
            key=value.get('external_id') or ('import-'+digest_record(normalized))
            if not isinstance(key,str) or not 1<=len(key)<=160: raise ValueError('external_id must be a bounded string')
            if key in seen: raise ValueError('duplicate external_id/content in import')
            seen.add(key); records.append({**normalized,'external_id':key})
        except (ValueError,TypeError) as exc: errors.append({'row':index,'message':str(exc)})
    return {'valid':not errors,'records':records,'errors':errors,'count':len(records),'input_sha256':hashlib.sha256(text.encode()).hexdigest()}
