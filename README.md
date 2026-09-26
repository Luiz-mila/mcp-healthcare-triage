# MCP Healthcare Triage Assistant

> 🚧 Work in progress — Step 1 of 8 (environment setup). Full documentation
> will be written in Step 7 of the build.

An MCP (Model Context Protocol) server that lets Claude query synthetic
patient records — history, current medications, and drug interactions —
in natural language, acting as a triage/EHR copilot.

## Stack
- Python 3.11
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) (v1.x)
- DuckDB
- Synthea (synthetic patient data generator)
- Docker

## Status
- [x] Project scaffold, requirements.txt, .gitignore, Docker setup
- [ ] Synthetic data generation (Synthea)
- [ ] DuckDB loading pipeline
- [ ] MCP server tools
- [ ] Claude Desktop integration
- [ ] Real-world test cases
- [ ] Full documentation
- [ ] Demo GIF/video
