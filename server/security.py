"""Bound actual ASGI body bytes, including requests without Content-Length."""
import re
from starlette.responses import JSONResponse

class RequestBodyLimit:
    def __init__(self, app, json_limit=256*1024, upload_limit=42*1024*1024):
        self.app=app;self.json_limit=json_limit;self.upload_limit=upload_limit

    async def __call__(self, scope, receive, send):
        if scope['type']!='http' or scope['method'] in {'GET','HEAD','OPTIONS'}:
            return await self.app(scope,receive,send)
        limit=self.upload_limit if re.fullmatch(r'/api/collections/\d+/upload',scope['path']) else self.json_limit
        messages=[];total=0
        while True:
            message=await receive()
            if message['type']=='http.disconnect':return
            total+=len(message.get('body',b''))
            if total>limit:
                return await JSONResponse({'detail':'Request too large'},413)(scope,receive,send)
            messages.append(message)
            if not message.get('more_body',False):break
        index=0
        async def bounded_receive():
            nonlocal index
            if index<len(messages):
                message=messages[index];index+=1;return message
            return await receive()
        await self.app(scope,bounded_receive,send)
