const Redis = require('ioredis');

let redisClient = null;
let isConnected = false;

const redisUrl = process.env.REDIS_URL;

if (redisUrl && redisUrl.trim()) {
  try {
    redisClient = new Redis(redisUrl, {
      lazyConnect: true,
      enableOfflineQueue: false,
      maxRetriesPerRequest: 1,
      connectTimeout: 5000,
      retryStrategy(times) {
        if (times > 5) {
          console.warn('[Redis] Max reconnect attempts reached. Redis caching will stay disabled.');
          return null; // Stop retrying
        }
        return Math.min(times * 300, 2000);
      },
    });

    redisClient.on('connect', () => {
      isConnected = true;
      console.log('[Redis] Connected successfully to Redis cluster/instance.');
    });

    redisClient.on('ready', () => {
      isConnected = true;
      console.log('[Redis] Client is ready to accept commands.');
    });

    redisClient.on('error', (err) => {
      isConnected = false;
      console.warn('[Redis Error] Connection or command failed (continuing without cache):', err.message);
    });

    redisClient.on('close', () => {
      isConnected = false;
    });

    // Attempt initial async connection without blocking server boot
    redisClient.connect().catch((err) => {
      isConnected = false;
      console.warn('[Redis] Initial connection failed. Operating gracefully without cache:', err.message);
    });
  } catch (err) {
    console.warn('[Redis] Failed to initialize Redis client:', err.message);
    redisClient = null;
    isConnected = false;
  }
} else {
  console.log('[Redis] No REDIS_URL provided. App is running gracefully with direct MongoDB/LLM execution.');
}

/**
 * Cache helper functions that safely degrade if Redis is unavailable.
 */
const cache = {
  isAvailable: () => isConnected && redisClient !== null,

  getClient: () => redisClient,

  async get(key) {
    if (!cache.isAvailable()) return null;
    try {
      const data = await redisClient.get(key);
      if (!data) return null;
      try {
        return JSON.parse(data);
      } catch {
        return data;
      }
    } catch (err) {
      console.warn(`[Redis Get Error] ${key}:`, err.message);
      return null;
    }
  },

  async set(key, value, ttlSeconds = 120) {
    if (!cache.isAvailable()) return false;
    try {
      const stringValue = typeof value === 'object' ? JSON.stringify(value) : String(value);
      if (ttlSeconds > 0) {
        await redisClient.set(key, stringValue, 'EX', ttlSeconds);
      } else {
        await redisClient.set(key, stringValue);
      }
      return true;
    } catch (err) {
      console.warn(`[Redis Set Error] ${key}:`, err.message);
      return false;
    }
  },

  async del(key) {
    if (!cache.isAvailable()) return false;
    try {
      await redisClient.del(key);
      return true;
    } catch (err) {
      console.warn(`[Redis Del Error] ${key}:`, err.message);
      return false;
    }
  },

  async delByPattern(pattern) {
    if (!cache.isAvailable()) return false;
    try {
      const stream = redisClient.scanStream({
        match: pattern,
        count: 50,
      });

      stream.on('data', async (keys) => {
        if (keys.length > 0) {
          const pipeline = redisClient.pipeline();
          keys.forEach((k) => pipeline.del(k));
          await pipeline.exec().catch(() => {});
        }
      });

      return true;
    } catch (err) {
      console.warn(`[Redis delByPattern Error] ${pattern}:`, err.message);
      return false;
    }
  },
};

module.exports = cache;

