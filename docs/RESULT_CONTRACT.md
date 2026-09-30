# 结果引用与独立校验

配置 config/result_contract.json 存在时，Web 结果审计和终验要求本协议。已有运行补登记保存的结果并运行校验即可，不因缺登记默认重跑耗时求解。新驱动需重启服务才生效；输入版本变化仍遵守 WORKFLOW_RELIABILITY 的保守失效规则。

## 生产与刷新（编码、稳健性阶段）

保存机器可读输出后写 results/metric-spec.json：schema_version=1，problem_id、run_id 标识当前题与批次；inputs 列出题面、数据，scripts 列出生产脚本；metrics 每项提供 id（英文小写起头）、label、unit、scenario、source（JSON相对路径）、pointer（如 /objective）、precision（0至12）。一项指标一个稳定ID，区分训练/样本外、利润/损失、可行解/最优值。统计量及单位换算在生产代码保存，不由写作阶段心算。

运行 python -m lib.result_contract build 后生成 registry.json，记录输入/脚本/来源哈希、原值和统一四舍五入显示值。生成物变化后重新build。

写 results/validation-spec.json：schema_version=1，kind，inputs（包含全部指标输入与来源及校验器依赖），checks_required（非空检查ID列表）。

- kind=linear：另给 problem、solution JSON路径。problem含 c、lower、upper（无界项null）、integer_indices、constraints（id,a,sense=le/ge/eq,rhs）。solution含 x、objective。独立重算每条约束、整数性和目标，不调用求解器；该线性规格需按已审核模型独立整理，不从求解器状态反推“通过”。
- kind=custom：另给 script Python路径、可选timeout_seconds（1至300）。脚本从原始数据与最终解独立计算约束/残差/目标，输出 JSON {"checks":[{"id":"...","passed":true,"evidence":"实际重算值与容差"}]}。禁止只转述 solver.success 或调用原求解器的同一检查函数；外部辅助模块也列入inputs。不得修改声明输入。此程序运行不提供操作系统沙箱，使用项目信任的校验脚本。

运行 python -m lib.result_contract validate，失败保持FAIL，不把数值不一致改成通过。可行性检查不证明全局最优，也不证明模型符合题意；非收敛解的排序不证明风险或相关性机制。结果审计仍需检查统计设计、求解界和结论强度。

## 写作与审查

写作运行 python -m lib.result_contract export，生成 paper/result-values.tex 与 result-values.json。在导言区引入 result-values.tex，并用 \ResultValue{指标ID} 引用核心数值。单位及情景须与registry一致。缺ID报错，修改引用文件会使审计失败。正文所有手写数值仍需人工对照；文件一致性不证明每处正文已使用宏。

结果审计只读运行 python -m lib.result_contract audit；终验另加 --rendered。检查来源哈希、覆盖范围、校验结果及引用文件；审查不替编码阶段补登记。所有检查仍需领域审核：自定义校验器独立性和覆盖是否充分不能单凭JSON证明。
