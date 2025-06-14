#!/bin/bash

# Exit on error
set -e

# Configuration
PROJECT_ID="eventify-460809"
SERVICE_NAME="search-service"
REGION="asia-southeast1"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
IMAGE_TAG="${TIMESTAMP}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting deployment process for ${SERVICE_NAME}...${NC}"

# Check if .env.prod file exists
if [ ! -f .env.prod ]; then
    echo -e "${RED}Error: .env.prod file not found${NC}"
    echo "Please create a .env.prod file based on env.template"
    exit 1
fi

# Generate service.yaml
echo -e "${YELLOW}Generating service.yaml...${NC}"
./generate-service-yaml.sh

# Build the Docker image with platform specification
echo -e "${YELLOW}Building Docker image for Linux platform...${NC}"
docker build --platform linux/amd64 -t ${IMAGE_NAME}:${IMAGE_TAG} .
docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${IMAGE_NAME}:latest

# Push the image to Google Container Registry
echo -e "${YELLOW}Pushing image to Google Container Registry...${NC}"
docker push ${IMAGE_NAME}:${IMAGE_TAG}
docker push ${IMAGE_NAME}:latest

# Update service.yaml with the new image tag
sed -i '' "s|${IMAGE_NAME}:latest|${IMAGE_NAME}:${IMAGE_TAG}|g" service.yaml

# Deploy to Cloud Run
echo -e "${YELLOW}Deploying to Cloud Run...${NC}"
gcloud run services replace service.yaml \
    --project=${PROJECT_ID} \
    --region=${REGION}

# Allow unauthenticated access
echo -e "${YELLOW}Setting up unauthenticated access...${NC}"
gcloud run services add-iam-policy-binding ${SERVICE_NAME} \
    --member="allUsers" \
    --role="roles/run.invoker" \
    --project=${PROJECT_ID} \
    --region=${REGION}

echo -e "${GREEN}Deployment completed successfully!${NC}"
echo -e "Service URL: $(gcloud run services describe ${SERVICE_NAME} --project=${PROJECT_ID} --region=${REGION} --format='value(status.url)')"
echo -e "Deployed image: ${IMAGE_NAME}:${IMAGE_TAG}" 