FROM openpolicyagent/opa:latest
# Copy policies from the same folder as this Dockerfile
COPY policies /policies
CMD ["run", "--server", "--addr", ":8181", "/policies"]
