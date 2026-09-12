# src/core/mcp_server.py
"""
Servidor MCP (Model Context Protocol) para exponer herramientas de AP0L0 a Claude Desktop, Cursor, etc.
Protocolo: JSON-RPC sobre stdio.
"""

import json
import sys
import threading
import inspect
from typing import Dict, Any, List, Callable, Optional


class MCPServer:
    """
    Servidor MCP que expone todas las herramientas registradas en el sistema.
    """
    
    def __init__(self, tool_registry: Dict[str, Callable]):
        self.tools = tool_registry
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
    def start(self):
        """Inicia el servidor en un hilo separado (stdio)."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print(f"[MCP] Servidor iniciado con {len(self.tools)} herramientas.")
        
    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
            
    def _run(self):
        """Bucle principal: lee de stdin, escribe a stdout."""
        while self._running:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                request = json.loads(line)
                response = self._handle_request(request)
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            except json.JSONDecodeError:
                # Ignorar líneas no JSON
                continue
            except Exception as e:
                sys.stderr.write(f"[MCP] Error: {e}\n")
                
    def _handle_request(self, request: Dict) -> Dict:
        """Maneja una solicitud JSON-RPC."""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")
        
        if method == "tools/list":
            return self._list_tools(request_id)
        elif method == "tools/call":
            return self._call_tool(params, request_id)
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            }
            
    def _list_tools(self, request_id: Any) -> Dict:
        """Lista todas las herramientas disponibles."""
        tools = []
        for name, func in self.tools.items():
            tools.append({
                "name": name,
                "description": (func.__doc__ or f"Tool: {name}").strip(),
                "parameters": {
                    "type": "object",
                    "properties": self._get_parameters(func)
                }
            })
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": tools}
        }
        
    def _call_tool(self, params: Dict, request_id: Any) -> Dict:
        """Ejecuta una herramienta."""
        name = params.get("name")
        arguments = params.get("arguments", {})
        if name not in self.tools:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": f"Tool '{name}' not found"}
            }
        try:
            result = self.tools[name](arguments)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": str(result)}]}
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32000, "message": str(e)}
            }
            
    def _get_parameters(self, func: Callable) -> Dict:
        """Extrae parámetros de la firma de la función."""
        sig = inspect.signature(func)
        params = {}
        for name, param in sig.parameters.items():
            # Ignorar parámetros especiales como self, player, speak, etc.
            if name in ("self", "player", "speak", "response", "session_memory", "parameters"):
                continue
            if param.default == inspect.Parameter.empty:
                params[name] = {
                    "type": "string",
                    "description": f"Parameter '{name}' (required)"
                }
            else:
                params[name] = {
                    "type": "string" if isinstance(param.default, str) else "number",
                    "description": f"Parameter '{name}' (default: {param.default})"
                }
        return params


def start_mcp_server(tool_registry: Dict[str, Callable]):
    """Función de conveniencia para iniciar el servidor MCP."""
    server = MCPServer(tool_registry)
    server.start()
    return server