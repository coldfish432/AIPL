# AIPL Electron Console

## Dev

```
cd ui-electron
npm install
npm run dev
```

## Build

```
npm run dist
```

## Resources

- Place the Java server at `ui-electron/resources/server.jar`.
- Optional: bundle a JRE at `ui-electron/resources/jre` (so `resources/jre/bin/java.exe` exists).

## Behavior

- Electron starts the Java server automatically.
- Closing Electron stops the Java server.
- Only localhost on port 18088 is used.
