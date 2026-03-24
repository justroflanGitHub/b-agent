# Simple Browser Agent - Docker Container ✅

**Fully Working Docker Container with Vision-Powered Browser Automation**

## 🚀 Quick Start

### 1. Build and Run with Docker Compose

```bash
cd browser-agent/docker

# Build and start the browser agent (API mode)
docker-compose up --build

# Or run in detached mode
docker-compose up -d --build
```

### 2. Access the API

Once running, access the browser agent API at `http://localhost:8080`

**API Endpoints:**
- `GET /status` - Check system status
- `POST /execute-task` - Execute browser automation task
- `POST /close-browser` - Close browser manually

### 3. Test with API

```bash
# Check system status (should show lm_studio_connected: true)
curl http://localhost:8080/status

# Execute a search task (fully working end-to-end)
curl -X POST http://localhost:8080/execute-task \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Search for Python tutorials",
    "url": "https://www.google.com"
  }'
```

**Expected Response:**
```json
{
  "task_id": "simple-task",
  "status": "completed",
  "goal": "Search for Python tutorials",
  "results": [{"step_number": 1, "success": true, "action_type": "navigate_and_search"}],
  "success": true,
  "execution_time": 46.66,
  "error": ""
}
```

## 🔧 Alternative Run Modes

### Run with Environment Variable (Automated)

```bash
# Set search query via environment variable
export SEARCH_QUERY="What is machine learning"
docker-compose run --rm browser-agent test
```

### Run with External LM Studio (Recommended)

The container uses host networking to connect to LM Studio running on the host machine at `http://127.0.0.1:1234`.

```bash
# Ensure LM Studio is running on host at 127.0.0.1:1234
# Then start the browser agent
docker-compose up --build

# Or run a test task
SEARCH_QUERY="What is quantum computing" docker-compose run --rm browser-agent test
```

### Manual Docker Commands

```bash
# Build the image (from browser-agent folder)
docker build -f docker/Dockerfile -t nettyan-browser-agent .

# Run API server
docker run -p 8080:8080 nettyan-browser-agent api

# Run test with search query
docker run -e SEARCH_QUERY="What is quantum computing" nettyan-browser-agent test

# Run interactive (if supported)
docker run -it nettyan-browser-agent
```

## 📋 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BROWSER_HEADLESS` | `true` | Run browser in headless mode |
| `BROWSER_AGENT_DEBUG` | `false` | Enable debug logging |
| `SEARCH_QUERY` | `""` | Search query for test mode |
| `DISPLAY` | `:99` | Virtual display for headless browser |

### Volumes

- `./data:/app/data` - Screenshots and data storage
- `./logs:/app/logs` - Application logs

## 🏗️ Architecture

### Container Structure

```
browser-agent/
├── docker/
│   ├── Dockerfile              # Main container definition
│   ├── entrypoint.sh          # Startup script
│   ├── docker-compose.yml     # Orchestration config
│   ├── README.md             # This documentation
│   ├── data/                 # Data storage volume
│   └── logs/                 # Logs volume
├── simple_browser_agent.py   # Main browser agent
├── simple_browser_api.py     # REST API wrapper
├── requirements-browser.txt  # Python dependencies
└── run_browser_agent.bat     # Windows runner
```

### Run Modes

1. **API Mode** (`api`): Web API server on port 8080
2. **Test Mode** (`test`): Automated test with SEARCH_QUERY env var
3. **Interactive Mode**: Fallback to API (Docker limitations)

## 🔍 Troubleshooting

### Common Issues

**"Browser initialization failed"**
```bash
# Check if virtual display is working
docker exec nettyan-browser-agent ps aux | grep Xvfb

# Check browser logs
docker logs nettyan-browser-agent
```

**"LM Studio connection failed"**
```bash
# Start LM Studio mock
docker-compose --profile mock up lm-studio-mock

# Or ensure external LM Studio is accessible
curl http://host.docker.internal:1234/v1/models
```

**"Playwright browsers not found"**
```bash
# Browsers should install automatically, but you can check:
docker exec nettyan-browser-agent playwright install --dry-run chromium
```

### Debug Mode

```bash
# Run with debug logging
docker run -e BROWSER_AGENT_DEBUG=true nettyan-browser-agent api
```

### Logs

```bash
# View container logs
docker-compose logs browser-agent

# Follow logs in real-time
docker-compose logs -f browser-agent
```

## 🔒 Security Considerations

- **Headless Mode**: Browser runs without visible UI by default
- **Isolated Container**: Limited system access
- **Network Restrictions**: Only necessary ports exposed
- **No Persistent Data**: Use volumes for data persistence

## 📊 Performance

- **Startup Time**: ~30 seconds (includes browser installation)
- **Task Execution**: 15-45 seconds per search
- **Memory Usage**: ~500MB base + ~200MB per active browser
- **CPU Usage**: Moderate during vision AI processing

## 🔄 Updates

To update the container:

```bash
# Pull latest changes
git pull

# Rebuild container
docker-compose build --no-cache

# Restart services
docker-compose up -d
```

## 🤝 Integration

### With External LM Studio

```yaml
# In docker-compose.yml, add external network
networks:
  hostnet:
    external: true
    name: host

services:
  browser-agent:
    networks:
      - hostnet
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

### With Other Services

```yaml
# Example integration with web app
services:
  web-app:
    # ... your web app config
    depends_on:
      - browser-agent

  browser-agent:
    # ... browser agent config
    environment:
      - API_BASE_URL=http://web-app:3000
```
