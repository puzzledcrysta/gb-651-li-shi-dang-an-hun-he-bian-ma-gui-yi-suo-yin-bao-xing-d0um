# 历史档案混合编码归一与索引保形

        面向一线复核人员的单服务数据工作台。样例数据随仓库提供，结论保留行号、原因码和原值。

        ## 业务模块

        - M1 文件采信：`/api/intake/run`
- M2 编码判定：`/api/encoding/detect`
- M3 字段保形：`/api/fields/normalize`
- M4 内容归一：`/api/content/normalize`
- M5 索引对账：`/api/reconcile`
- M6 批次导出：`/api/export/evidence.csv`

        ## 核心规则

        候选解码必须完整且无替换字符；档号、盒号与超大流水号始终按字符串逐字保留。

        ## 题名对账

        档号按字符串逐字匹配。题名只归一可直接核过的写法差异：空白字符折叠、全角/半角宽度折叠。
        不启用 NFKC 兼容分解，`附件①` 不会因为 NFKC 变成 `附件1` 而与 `附件1` 判为同一份；
        这类差异标记为 `REVIEW`（`TITLE_UNCERTAIN`），两侧原题名同时保留，交由人工裁决。

        差异分类：

        - `SAME`：题名逐字一致。
        - `STYLE`：仅空格或全半角写法不同，可直接核过（`TITLE_STYLE_ONLY`）。
        - `REVIEW`：拿不准的差异，包括兼容字符（`TITLE_UNCERTAIN`）、单侧缺题名（`TITLE_ONE_SIDED`）、
          同一档号多值（`TITLE_DUPLICATE_CONFLICT`）。
        - `MISSING` / `ORPHAN`：档号只在一侧存在（`MISSING_IN_TRANSFER` / `ORPHAN_IN_INDEX`）。

        批次导出逐条给出两侧原题名、归一题名、差异分类、原因码、行号与规则版本，复核时能看出核对依据。

        ## 启动

        ```bash
        docker compose up --build
        ```

        浏览器访问 `http://localhost:18210`。运行测试：

        ```bash
        docker compose exec -T app pytest -q
        ```

        ## 样例流程

        依次运行六个模块；最后在批次页复核输入、有效、隔离与输出合计。同一输入摘要重复执行时复用原 `run_id`。
        对账批次由 `/api/reconcile` 写入；查看页面与导出证据都不新增批次。

        ## 已知不覆盖

        不处理加密文件与需要外部密钥的对象；不连接真实生产存储。
