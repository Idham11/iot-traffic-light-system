-- Table to store user credentials
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table to log traffic system events and statuses
CREATE TABLE IF NOT EXISTS system_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL, -- e.g., 'LOGIN', 'TRAFFIC_LIGHT_UPDATE', 'VEHICLE_DETECTED'
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table to log traffic decisions based on priority algorithm
CREATE TABLE IF NOT EXISTS decision_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    lane_a_count INTEGER NOT NULL,
    lane_b_count INTEGER NOT NULL,
    lane_c_count INTEGER NOT NULL,
    selected_lane VARCHAR(10) NOT NULL,
    priority_score INTEGER NOT NULL,
    green_duration INTEGER NOT NULL,
    reason TEXT
);

CREATE TABLE IF NOT EXISTS latest_status (
    id INT PRIMARY KEY,
    active_lane VARCHAR(10),
    lane_a_light VARCHAR(10),
    lane_a_count INT,
    lane_a_wait_time INT,
    lane_a_priority INT,
    lane_b_light VARCHAR(10),
    lane_b_count INT,
    lane_b_wait_time INT,
    lane_b_priority INT,
    lane_c_light VARCHAR(10),
    lane_c_count INT,
    lane_c_wait_time INT,
    lane_c_priority INT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
