#!/bin/bash

# Parse command line arguments
OUTPUT_FILE="test/test_new_codegen.py"
VIEWPORT_SIZE="1920,1080"
VIEWPORT_SIZE="1280,720"
while [[ $# -gt 0 ]]; do
    case $1 in
    -o | --output)
        OUTPUT_FILE="$2"
        shift 2
        ;;
    *)
        echo "Unknown option: $1"
        echo "Usage: $0 [-o|--output <test_file>] [-v|--viewport <width,height>]"
        echo "  -o, --output: Output test file (default: test/test_new_codegen.py)"
        exit 1
        ;;
    esac
done

echo "Output file: $OUTPUT_FILE"
echo "Viewport size: $VIEWPORT_SIZE"

# Backup and prepare environment
if [ -f .env ]; then
    mv .env .env.bak
fi

cp env_test .env

# Assure DEBUG=0 no reload of code during test generation
sed -i 's/^DEBUG=.*/DEBUG=0/' .env
source .env
# Stop and remove any existing containers
docker compose down 2>/dev/null || true

# Start all services with docker compose (detached mode)
docker compose up -d

echo "Waiting for Cosmonaut to start..."
sleep 3

echo "http://localhost:$FLASK_PORT"
# Check if app is running
until curl -s "http://localhost:$FLASK_PORT" >/dev/null 2>&1; do
    echo "Still waiting for Dash app..."
    sleep 1
done

echo "Dash app is running at http://localhost:$FLASK_PORT"
echo ""
echo "==============================================="
echo "Starting Playwright Codegen"
echo "==============================================="
echo ""
echo "Configuration:"
echo "  Viewport: $VIEWPORT_SIZE pixels"
echo "  Output: $OUTPUT_FILE"
echo ""
echo "Instructions:"
echo "1. A browser window will open showing your app"
echo "2. Interact with your app (click, type, navigate)"
echo "3. Playwright will record your actions"
echo "4. Close the browser when done"
echo "5. The generated test will be saved to: $OUTPUT_FILE"
echo ""
echo "Press Enter to start codegen..."
read

# Run playwright codegen with specified viewport size
uv run playwright codegen --viewport-size="$VIEWPORT_SIZE" -o "$OUTPUT_FILE" http://localhost:$FLASK_PORT

echo ""
echo "Cleaning up..."
docker compose down

# Restore original .env
if [ -f .env.bak ]; then
    mv .env.bak .env
fi
