ARG NODE_BASE_IMAGE=docker.m.daocloud.io/library/node:20-alpine
FROM ${NODE_BASE_IMAGE}

WORKDIR /app

COPY package.json package-lock.json* pnpm-lock.yaml* ./
RUN npm install

COPY . .

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
