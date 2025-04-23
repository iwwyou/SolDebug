import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List
from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
from Analyzer.ContractAnalyzer import ContractAnalyzer
from antlr4 import *
from Parser.SolidityLexer import SolidityLexer
from Parser.SolidityParser import SolidityParser

app = FastAPI()
contract_analyzer = ContractAnalyzer()

# 클라이언트 연결을 관리하는 클래스
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


def map_context_type(context_type):
    context_mapping = {
        'contract': 'interactiveSourceUnit',
        'library': 'interactiveSourceUnit',
        'interface': 'interactiveSourceUnit',
        'enum': 'interactiveSourceUnit',
        'struct': 'interactiveSourceUnit',
        'function': 'interactiveSourceUnit',
        'constructor': 'interactiveSourceUnit',
        'fallback': 'interactiveSourceUnit',
        'receive': 'interactiveSourceUnit',
        'event': 'interactiveSourceUnit',
        'error': 'interactiveSourceUnit',
        'modifier': 'interactiveSourceUnit',
        'stateVariableDeclaration': 'interactiveSourceUnit',
        'enumMember': 'interactiveEnumUnit',
        'structMember': 'interactiveStructUnit',
        'simpleStatement': 'interactiveBlockUnit',
        'if': 'interactiveBlockUnit',
        'for': 'interactiveBlockUnit',
        'while': 'interactiveBlockUnit',
        'do': 'interactiveBlockUnit',
        'try': 'interactiveBlockUnit',
        'return': 'interactiveBlockUnit',
        'break': 'interactiveBlockUnit',
        'continue': 'interactiveBlockUnit',
        'emit': 'interactiveBlockUnit',
        'doWhileWhile': 'interactiveDoWhileUnit',
        'catch': 'interactiveCatchClauseUnit',
        'else_if': 'interactiveIfElseUnit',
        'else': 'interactiveIfElseUnit'
    }

    try:
        return context_mapping[context_type]
    except KeyError:
        print(f"Warning: No mapping found for context_type '{context_type}'. Returning None.")
        return None


def generate_parse_tree(input_stream, context_type):
    input_stream = InputStream(input_stream)
    lexer = SolidityLexer(input_stream)
    token_stream = CommonTokenStream(lexer)
    parser = SolidityParser(token_stream)

    context_rule = map_context_type(context_type)

    if context_rule == 'interactiveStructUnit':
        tree = parser.interactiveStructUnit()
    elif context_rule == 'interactiveEnumUnit':
        tree = parser.interactiveEnumUnit()
    elif context_rule == 'interactiveBlockUnit':
        tree = parser.interactiveBlockUnit()
    elif context_rule == 'interactiveDoWhileUnit':
        tree = parser.interactiveDoWhileUnit()
    elif context_rule == 'interactiveIfElseUnit':
        tree = parser.interactiveIfElseUnit()
    elif context_rule == 'interactiveCatchClauseUnit':
        tree = parser.interactiveCatchClauseUnit()
    else:
        tree = parser.interactiveSourceUnit()

    return tree


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            code = message['code']
            start_line = message['startLine']
            end_line = message['endLine']

            contract_analyzer.update_code(start_line, end_line, code)
            context_type = contract_analyzer.get_current_context_type()

            # Parse the received code based on context_type
            tree = generate_parse_tree(code, context_type) # 어떤 문법규칙으로 파싱할건지

            visitor = EnhancedSolidityVisitor(contract_analyzer)
            visitor.visit(tree)

            # Send analysis result back to the client
            result = contract_analyzer.get_analysis_result()
            await manager.send_personal_message(json.dumps(result), websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)