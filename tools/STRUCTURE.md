# kit-tools — Structure

Flat community toolset located at `ai-factory/kit-tools/`.

## Layout
```
kit-tools/
├── *.py            # Python tools (community set)
├── web.sh          # convenience launcher
├── README.md       # usage and installation guide
└── test/           # self-tests
```

## Portability
All tools use environment variables (see `.env.example`) for configuration.
No hardcoded paths — works from any location after `pip install` of dependencies.
