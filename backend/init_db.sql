    -- 创建数据库
    CREATE DATABASE IF NOT EXISTS production_monitor 
    CHARACTER SET utf8mb4 
    COLLATE utf8mb4_unicode_ci;

    USE production_monitor;

    -- 检测记录表
    CREATE TABLE IF NOT EXISTS detection_records (
        id INT AUTO_INCREMENT PRIMARY KEY,
        device_id VARCHAR(50) NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        person_count INT DEFAULT 0,
        in_danger_zone BOOLEAN DEFAULT FALSE,
        alert_triggered BOOLEAN DEFAULT FALSE,
        image_path VARCHAR(255),
        details TEXT,
        INDEX idx_device_id (device_id),
        INDEX idx_timestamp (timestamp)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

    -- 传感器数据表
    CREATE TABLE IF NOT EXISTS sensor_data (
        id INT AUTO_INCREMENT PRIMARY KEY,
        device_id VARCHAR(50) NOT NULL,
        sensor_type VARCHAR(20) NOT NULL COMMENT 'temperature/pressure/humidity',
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        value FLOAT NOT NULL,
        unit VARCHAR(10),
        INDEX idx_device_sensor (device_id, sensor_type),
        INDEX idx_timestamp (timestamp)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

    -- 生产状态表
    CREATE TABLE IF NOT EXISTS production_status (
        id INT AUTO_INCREMENT PRIMARY KEY,
        device_id VARCHAR(50) NOT NULL UNIQUE,
        status VARCHAR(20) DEFAULT 'stopped' COMMENT 'running/stopped/paused',
        mode VARCHAR(20) DEFAULT 'product_a' COMMENT 'product_a/product_b',
        production_count INT DEFAULT 0,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_device_id (device_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

    -- 报警记录表
    CREATE TABLE IF NOT EXISTS alert_records (
        id INT AUTO_INCREMENT PRIMARY KEY,
        device_id VARCHAR(50) NOT NULL,
        alert_type VARCHAR(20) NOT NULL COMMENT 'intrusion/temperature/pressure',
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        message VARCHAR(255),
        level VARCHAR(10) DEFAULT 'warning' COMMENT 'info/warning/danger',
        resolved BOOLEAN DEFAULT FALSE,
        INDEX idx_device_id (device_id),
        INDEX idx_resolved (resolved),
        INDEX idx_timestamp (timestamp)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

    -- 插入默认设备状态
    INSERT INTO production_status (device_id, status, mode, production_count) 
    VALUES ('device_001', 'stopped', 'product_a', 0)
    ON DUPLICATE KEY UPDATE device_id = device_id;
