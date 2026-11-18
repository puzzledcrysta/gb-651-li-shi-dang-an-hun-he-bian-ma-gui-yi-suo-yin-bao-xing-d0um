# 数据字典

| 字段 | 类型 | 可空 | 定义 |
|---|---|---:|---|
| `run_id` | string | 否 | 输入摘要派生的稳定运行编号 |
| `source_line` | integer | 否 | 原文件物理行号 |
| `reason_code` | string | 是 | 隔离或冲突的稳定原因码 |
| `raw_value` | string | 是 | 未归一的原始证据 |
| `normalized_value` | string | 是 | 按项目规则得到的值 |
| `rule_version` | string | 否 | 计算规则版本 |
| `archive_id` | string | 否 | 档号，逐字保留的字符串 |
| `index_title_raw` | string | 是 | 索引侧原题名，不做改写 |
| `transfer_title_raw` | string | 是 | 移交表侧原题名，不做改写 |
| `index_title_normalized` | string | 是 | 索引侧归一题名（仅折叠空白与全半角） |
| `transfer_title_normalized` | string | 是 | 移交表侧归一题名（仅折叠空白与全半角） |
| `difference_class` | string | 否 | `SAME` / `STYLE` / `REVIEW` / `MISSING` / `ORPHAN` / `NO_TITLE` |
| `detail` | string | 是 | 差异来源：`width` / `whitespace` / `width+whitespace` / `content` / `duplicate` / `none` |
| `status` | string | 否 | 对账行状态：`MATCHED` / `MISSING` / `ORPHAN` |
| `source_side` | string | 是 | 导出时 `source_line` 取自哪一侧：`index` / `transfer` |
| `reason_text` | string | 是 | 原因码的中文说明，便于复核人员直接阅读 |

字符串编号逐字保留。金额与计量值用 `Decimal`。时间值带偏移并以 UTC 参与比较。区间统一采用左闭右开。

题名归一不使用 NFKC：`①`、`㈠`、`Ⅷ` 等兼容字符保持原样，避免把不同原件认成同一份。
