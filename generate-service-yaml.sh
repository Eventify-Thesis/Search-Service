#!/bin/bash

# Configuration
PROJECT_ID="eventify-460809"
SERVICE_NAME="search-service"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Generate Cloud Run service.yaml from .env file
cat > service.yaml << EOF
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: ${SERVICE_NAME}
  annotations:
    run.googleapis.com/ingress: all
spec:
  template:
    metadata:
      annotations:
        run.googleapis.com/execution-environment: gen2
        run.googleapis.com/vpc-access-connector: eventify-connector
        run.googleapis.com/vpc-access-egress: private-ranges-only
    spec:
      containerConcurrency: 10
      timeoutSeconds: 300
      containers:
      - image: ${IMAGE_NAME}:latest
        ports:
        - name: http1
          containerPort: 8080
        env:
        - name: NODE_ENV
          value: "production"
EOF

# Read .env file and append environment variables
if [ -f .env.prod ]; then
    while IFS='=' read -r key value; do
        # Skip empty lines, comments, and reserved environment variables
        if [[ ! -z "$key" && ! "$key" =~ ^[[:space:]]*# && "$key" != "PORT" ]]; then
            # Remove any trailing whitespace and quotes
            key=$(echo "$key" | xargs)
            value=$(echo "$value" | xargs | sed 's/^"\(.*\)"$/\1/')
            
            echo "        - name: $key" >> service.yaml
            echo "          value: \"$value\"" >> service.yaml
        fi
    done < .env.prod
fi

# Add resource limits - ML workloads need more memory
cat >> service.yaml << 'EOF'
        resources:
          limits:
            cpu: "4000m"
            memory: "8Gi"
EOF

echo "Generated service.yaml with environment variables from .env.prod file" 