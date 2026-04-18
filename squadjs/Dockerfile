FROM node:18-bookworm-slim

WORKDIR /app

COPY package.json yarn.lock ./
COPY assets ./assets
COPY core ./core
COPY squad-server ./squad-server
COPY index.js bridge-server.js config.oasis-template.json CMP_SETUP.md ./

RUN corepack enable && yarn install --frozen-lockfile --ignore-engines

EXPOSE 3001

CMD ["node", "index.js"]
