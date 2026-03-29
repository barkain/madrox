---
name: dashboard
description: Open the Madrox Monitor dashboard in the browser
user_invocable: true
---

Open the Madrox Monitor dashboard in the default browser, reading the frontend port from the session port file.

```bash
PORT_FILE=$(ls -t /tmp/madrox_logs/*/session_ports.env 2>/dev/null | head -1)
FE_PORT=$(grep FE_PORT "$PORT_FILE" 2>/dev/null | cut -d= -f2)
FE_PORT=${FE_PORT:-3002}
open "http://localhost:$FE_PORT" 2>/dev/null || xdg-open "http://localhost:$FE_PORT" 2>/dev/null
```

Tell the user the dashboard is opening at http://localhost:$FE_PORT.
