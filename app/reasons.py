REASONS = {
    "BAD_COLUMNS": "字段数量不符", "EMPTY_VALUE": "必要值为空",
    "DUPLICATE_CONFLICT": "同一业务键取值冲突", "TRUNCATED": "尾记录不完整",
    "INVALID_VALUE": "值不符合定义", "STALE_VERSION": "提交版本已过期",
    "TITLE_MATCH": "题名一致",
    "TITLE_STYLE_ONLY": "仅空格或全半角写法差异，可直接核对",
    "TITLE_UNCERTAIN": "题名不同，需人工判断是否同一份原件",
    "TITLE_ONE_SIDED": "只有一侧提供题名，无法互证",
    "TITLE_DUPLICATE_CONFLICT": "同一档号出现多个不同题名",
    "TITLE_NOT_PROVIDED": "两侧均未提供题名",
    "MISSING_IN_TRANSFER": "索引有档号，移交表缺失",
    "ORPHAN_IN_INDEX": "移交表有档号，索引缺失",
    "NO_RECONCILE": "还没有可导出的对账批次",
}

def reason(code: str) -> str:
    return REASONS.get(code, "未登记原因")
