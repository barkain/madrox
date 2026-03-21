---
name: dashboard
description: Open the Madrox Monitor dashboard in the browser
user_invocable: true
---

Open the Madrox Monitor dashboard at http://localhost:3002 in the default browser.

```bash
open "http://localhost:3002" 2>/dev/null || xdg-open "http://localhost:3002" 2>/dev/null
```

Tell the user the dashboard is opening at http://localhost:3002.
