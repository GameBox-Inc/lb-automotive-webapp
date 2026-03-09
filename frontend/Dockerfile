FROM node:20-alpine

# Set working directory and non-root user
WORKDIR /app
RUN chown node:node /app

# Switch to non-root user
USER node

COPY --chown=node:node package*.json ./

RUN npm install

COPY --chown=node:node . .

EXPOSE 5173

# Bind to 0.0.0.0 to ensure container accessibility
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
