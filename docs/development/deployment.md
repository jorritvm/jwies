# Deployment instructies

Deze file gaat over deployment. Het opzetten van de zogenaamde productie omgeving.
- continu running servers
- native clients (UI applications)

<!-- TOC -->
* [Deployment instructies](#deployment-instructies)
  * [jwies-server](#jwies-server)
  * [jwies-qt-client](#jwies-qt-client)
  * [jwies-web-client](#jwies-web-client)
<!-- TOC -->

## jwies-server
De server is een gewone ASGI-toepassing en blijft onbeperkt draaien.

```powershell
uv run --project jwies-server jwies-server `
    --config /etc/jwies/server.yaml `
    --log-file /var/log/jwies.log
```

Om online te spelen zonder netwerkproblemen zijn meerdere mogelijkheden:
- open poort 8000 in je firewall
- zet een reverse proxy op

> todo: docker

## jwies-qt-client
> todo
 
## jwies-web-client
> todo
