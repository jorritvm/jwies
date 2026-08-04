# Op een homeserver zetten

De server is een gewone ASGI-toepassing en blijft onbeperkt draaien.

```powershell
uv run --package jwies-server jwies-server `
    --config /etc/jwies/server.yaml `
    --log-file /var/log/jwies.log
```

Zet er een reverse proxy voor als je van buitenaf wil spelen, en gebruik dan
`https`/`wss`: de webclient kiest zijn schema op basis van de pagina waarop hij
geladen is.
