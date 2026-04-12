
import winston from 'winston';
import path from 'path';
import fs from 'fs';

const LOG_DIR = path.join(process.cwd(), 'logs');
if (!fs.existsSync(LOG_DIR)) fs.mkdirSync(LOG_DIR, { recursive: true });

const { combine, timestamp, colorize, printf, json, errors } = winston.format;

// Human-readable format for console
const consoleFormat = printf(({ level, message, timestamp: ts, ...meta }) => {
  const metaStr = Object.keys(meta).length ? ` ${JSON.stringify(meta)}` : '';
  return `${ts} | ${level.padEnd(17)} | ${message}${metaStr}`;
});

const logger = winston.createLogger({
  level: process.env.LOG_LEVEL ?? 'info',
  defaultMeta: { service: 'endoscopy-frontend' },
  transports: [
    // Console — colourised, concise
    new winston.transports.Console({
      format: combine(
        colorize({ all: true }),
        timestamp({ format: 'HH:mm:ss' }),
        errors({ stack: true }),
        consoleFormat,
      ),
    }),
    // File — JSON, error-level only
    new winston.transports.File({
      filename: path.join(LOG_DIR, 'error.log'),
      level: 'error',
      format: combine(timestamp(), errors({ stack: true }), json()),
    }),
    // File — JSON, all levels
    new winston.transports.File({
      filename: path.join(LOG_DIR, 'combined.log'),
      format: combine(timestamp(), errors({ stack: true }), json()),
    }),
  ],
});

export default logger;
