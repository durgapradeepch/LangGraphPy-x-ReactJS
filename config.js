// Configuration for MCP Server
require('dotenv').config();

module.exports = {
    // Server Configuration
    SERVER_PORT: process.env.SERVER_PORT || 3001,

    // Neo4j Configuration
    NEO4J_CONFIG: {
        host: process.env.NEO4J_HOST || '127.0.0.1',
        port: parseInt(process.env.NEO4J_BOLT_PORT) || 7687,
        username: process.env.NEO4J_USER || 'neo4j',
        password: process.env.NEO4J_PASSWORD || 'testing@neo4j',
        database: process.env.NEO4J_DATABASE || 'neo4j'
    },

    // OpenAI Configuration
    OPENAI_API_KEY: process.env.OPENAI_API_KEY || '',
    LLM_CHOICE: process.env.LLM_CHOICE || 'openai',
    MODEL_NAME: process.env.MODEL_NAME || 'gpt-4o',

    // VictoriaMetrics Configuration
    VICTORIA_METRICS_URL: process.env.VICTORIA_METRICS_URL || 'http://localhost:8428',

    // VictoriaLogs Configuration
    VICTORIA_LOGS_URL: process.env.VICTORIA_LOGS_API_URL || process.env.VICTORIA_LOGS_URL || 'http://localhost:9428',

    // Manifest API Configuration
    MANIFEST_API_URL: process.env.MANIFEST_API_URL || 'http://localhost:8080',
    MANIFEST_API_KEY: process.env.MANIFEST_API_KEY || '',
    MANIFEST_ORG_KEY: process.env.MANIFEST_ORG_KEY || 'dev',

    // Llama API Configuration (if using Llama)
    LLAMA_API_ENDPOINT: process.env.LLAMA_API_ENDPOINT || '',
    LLAMA_API_KEY: process.env.LLAMA_API_KEY || '',

    // Feature Flags
    STREAM: process.env.STREAM || 'false',
    TOKENIZERS_PARALLELISM: process.env.TOKENIZERS_PARALLELISM || 'false'
};
