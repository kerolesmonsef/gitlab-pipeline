GITLAB_URL="https://git.foo.mobi"
DEFAULT_PROJECT_PATH="adc/backends/project-name"
BRANCH="staging"

if [[ -f .env ]]; then
  source .env
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-path)
      DEFAULT_PROJECT_PATH="$2"
      shift 2
      ;;
    --branch)
      BRANCH="$2"
      shift 2
      ;;
    *)
      echo "❌ Unknown argument: $1"
      exit 1
      ;;
  esac
done

PROJECT_PATH="${DEFAULT_PROJECT_PATH//\//%2F}"
DEPLOY="${DEPLOY:-true}"
POSTMAN_TESTS="${POSTMAN_TESTS:-false}"
SONAR_TESTS="${SONAR_TESTS:-false}"
JMETER_LOAD_TEST="${JMETER_LOAD_TEST:-false}"
JMETER_INTERNAL="${JMETER_INTERNAL:-false}"
JMETER_EXTERNAL="${JMETER_EXTERNAL:-false}"
DOCKER_CACHE="${DOCKER_CACHE:-false}"

if [[ -z "$GITLAB_TOKEN" ]]; then
  echo "❌ GITLAB_TOKEN is not set."
  exit 1
fi

echo "🚀 Triggering pipeline on '$BRANCH'..."

RESPONSE=$(curl --silent --write-out "\n%{http_code}" \
  --request POST \
  --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  --header "Content-Type: application/json" \
  --data "{\"ref\": \"refs/heads/$BRANCH\", \"variables\": [{\"key\": \"DEPLOY\", \"value\": \"$DEPLOY\"}, {\"key\": \"POSTMAN_TESTS\", \"value\": \"$POSTMAN_TESTS\"}, {\"key\": \"SONAR_TESTS\", \"value\": \"$SONAR_TESTS\"}, {\"key\": \"JMETER_LOAD_TEST\", \"value\": \"$JMETER_LOAD_TEST\"}, {\"key\": \"JMETER_INTERNAL\", \"value\": \"$JMETER_INTERNAL\"}, {\"key\": \"JMETER_EXTERNAL\", \"value\": \"$JMETER_EXTERNAL\"}, {\"key\": \"DOCKER_CACHE\", \"value\": \"$DOCKER_CACHE\"}]}" \
  "$GITLAB_URL/api/v4/projects/$PROJECT_PATH/pipeline")

HTTP_STATUS=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [[ "$HTTP_STATUS" == "201" ]]; then
  PIPELINE_URL=$(echo "$BODY" | grep -o '"web_url":"[^"]*"' | head -1 | cut -d'"' -f4)
  echo "✅ Pipeline created: $PIPELINE_URL"
else
  echo "❌ Failed (HTTP $HTTP_STATUS): $BODY"
  exit 1
fi