# Troubleshooting chatwoot-bridge

## The container keeps restarting
Check docker logs <container-name>. A common cause is the LLM endpoint
being unreachable — confirm LLM_API_BASE is correct and the LLM server
is actually running and network-exposed (not bound to localhost only).

## Drafted replies say "I don't have specific information"
This means nothing relevant was found in the vector memory yet. Ingest
more documentation and past resolved conversations — answer quality
improves as more real content is added, not by changing configuration.

## Windows-hosted LLM unreachable from Linux
Confirm the Windows machine's network profile is set to "Private," not
"Public" — Windows can silently block inbound connections on Public
networks even with a matching firewall rule in place.
