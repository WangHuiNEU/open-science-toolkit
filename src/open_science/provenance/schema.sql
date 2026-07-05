-- Open Science 溯源库 schema
-- 照搬 operon self-awareness 的表结构（../extracted/skills/self-awareness/SKILL.md）。
-- 约定与 operon 一致：
--   * 时间戳一律 epoch 毫秒（INTEGER）
--   * 布尔用 0/1（INTEGER）
--   * JSON 列用 TEXT，读取时 json_extract
-- 本阶段只落"溯源 by construction"必需的核心表；多租户/校验/远程算力等
-- 表（session_claims / verification_checks / compute_usage / memories …）
-- 留到用到的阶段（2/5）再补，不做提前抽象。

-- ── 会话 / 帧 ────────────────────────────────────────────────
-- 一次 agent 运行 = 一个 frame（根会话或被委派的子 agent）。
CREATE TABLE IF NOT EXISTS frames (
    id                   TEXT PRIMARY KEY,
    parent_frame_id      TEXT,
    root_frame_id        TEXT,
    agent_name           TEXT,
    delegate_name        TEXT,
    status               TEXT,          -- processing/completed/failed/cancelled/...
    model                TEXT,
    effort               TEXT,
    input_tokens         INTEGER DEFAULT 0,
    output_tokens        INTEGER DEFAULT 0,
    cache_read_tokens    INTEGER DEFAULT 0,
    cache_write_tokens   INTEGER DEFAULT 0,
    total_cost           REAL    DEFAULT 0,
    task_summary         TEXT,
    status_description   TEXT,
    conversation_type    TEXT,
    name                 TEXT,
    project_id           TEXT,
    input_data           TEXT,          -- JSON
    output_data          TEXT,          -- JSON, $.response 为最终回复
    context_data         TEXT,          -- JSON, 运行态快照
    mentioned_artifact_ids TEXT,        -- JSON
    created_at           INTEGER,
    updated_at           INTEGER,
    completed_at         INTEGER,
    last_user_message_at INTEGER,
    is_hidden            INTEGER DEFAULT 0
);

-- ── artifacts ───────────────────────────────────────────────
-- 一个文件一行；具体版本在 artifact_versions。
CREATE TABLE IF NOT EXISTS artifacts (
    id                TEXT PRIMARY KEY,
    project_id        TEXT,
    root_frame_id     TEXT,
    frame_id          TEXT,
    filename          TEXT NOT NULL,
    latest_version_id TEXT,
    is_user_upload    INTEGER DEFAULT 0,
    is_ephemeral      INTEGER DEFAULT 0,
    folder_id         TEXT,
    sort_order        INTEGER,
    priority          INTEGER,
    created_at        INTEGER
);

-- 一次保存 = 一个版本。checksum / environment_snapshot / lineage 全在这。
CREATE TABLE IF NOT EXISTS artifact_versions (
    id                    TEXT PRIMARY KEY,
    artifact_id           TEXT NOT NULL,
    version_number        INTEGER NOT NULL,
    frame_id              TEXT,
    content_type          TEXT,          -- MIME，渲染层据此分派
    size_bytes            INTEGER,
    checksum              TEXT,          -- sha256(content)
    storage_path          TEXT,          -- 落盘路径
    extracted_code        TEXT,
    code_description      TEXT,
    language              TEXT,
    agent_name            TEXT,
    is_intermediate       INTEGER DEFAULT 0,
    is_checkpoint         INTEGER DEFAULT 0,
    parent_version_id     TEXT,
    producing_cell_id     TEXT,          -- → execution_log.id
    lineage_messages      TEXT,          -- JSON
    dependency_mappings   TEXT,          -- JSON
    environment_snapshot  TEXT,          -- JSON
    annotations           TEXT,          -- JSON
    cell_sources          TEXT,          -- JSON
    created_at            INTEGER,
    FOREIGN KEY (artifact_id) REFERENCES artifacts(id)
);

-- artifact DAG 边：B 依赖 A。
CREATE TABLE IF NOT EXISTS artifact_dependencies (
    artifact_version_id   TEXT NOT NULL,   -- 下游 B
    depends_on_version_id TEXT NOT NULL,   -- 上游 A
    reference_name        TEXT,
    PRIMARY KEY (artifact_version_id, depends_on_version_id)
);

-- 内容寻址去重存储：多个版本相同内容只存一份。
CREATE TABLE IF NOT EXISTS content_snapshots (
    hash       TEXT PRIMARY KEY,          -- sha256
    content    BLOB,
    size_bytes INTEGER
);

-- ── 执行历史 ────────────────────────────────────────────────
-- 每个 python/r/bash/repl cell 一行，按序。这是"跑了什么"的真相。
CREATE TABLE IF NOT EXISTS execution_log (
    id            TEXT PRIMARY KEY,
    frame_id      TEXT,
    cell_index    INTEGER,               -- 单调递增
    kernel_id     TEXT,
    kernel_kind   TEXT,                  -- analysis/operon
    conda_env     TEXT,
    language      TEXT,
    source        TEXT,                  -- 提交的原代码
    stdout        TEXT,
    stderr        TEXT,
    exit_status   TEXT,                  -- ok/error/kernel_died/cancelled
    error_lineno  INTEGER,
    files_written TEXT,                  -- JSON [{path, sha256}]
    created_at    INTEGER
);

-- cell 内每次 host.* SDK 调用一行。
CREATE TABLE IF NOT EXISTS host_call_log (
    id               TEXT PRIMARY KEY,
    execution_log_id TEXT,               -- → execution_log.id
    seq              INTEGER,
    method           TEXT,               -- query_db/llm/mcp/...
    args_json        TEXT,
    derivable        INTEGER,
    data_inline      TEXT,
    data_ref         TEXT,
    error            TEXT,
    bytes            INTEGER,
    created_at       INTEGER
);

-- 常用索引
CREATE INDEX IF NOT EXISTS idx_exec_frame     ON execution_log(frame_id, cell_index);
CREATE INDEX IF NOT EXISTS idx_ver_artifact   ON artifact_versions(artifact_id, version_number);
CREATE INDEX IF NOT EXISTS idx_hostcall_exec  ON host_call_log(execution_log_id, seq);
CREATE INDEX IF NOT EXISTS idx_dep_downstream ON artifact_dependencies(artifact_version_id);
