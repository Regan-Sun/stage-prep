# Codex 与 WorkBuddy 适配

共用：课程规则、两种模式、数据格式、Python 脚本、案例索引。不要在共用正文要求执行平台特定 MCP 名称或绝对解释器路径。

Codex：界面显示信息在 agents/openai.yaml；使用宿主提供的文件、命令执行与图片查看工具。安装到当前实例实际发现的个人 Skill 目录，确认无同名覆盖。

WorkBuddy：使用宿主现有文件、图片查看和命令执行能力。不同模型的图像输入可用性需实际检查。官方技能格式同样采用 SKILL.md 和可选 references/scripts；公开平台分发还可能需要 display_name、description_zh、description_en、category、version、author 等元数据。实际分发时按当前安装入口验证，不将 Codex 的 openai.yaml 当作 WorkBuddy 显示配置。

迁移最小验证：

1. 能调用并加载两种模式及课程参考文件。
2. 同一稿件的原文完整保留，拒绝词不会机械映射手势，坐姿/单手约束成立。
3. 能读取本机视频、抽帧并实际查看图片，不只是列出文件路径。
4. 能按实际音频/字幕条件输出复盘，证据不足时缩小范围。
5. 导出报告图片可打开，时间码可回溯，当前句加粗。

上述实测完成前，WorkBuddy 状态只能写“待迁移实测”。共用源修改一次，两个平台版本都从同一源更新。

官方参考（开发时核对）：
- https://learn.chatgpt.com/docs/build-skills
- https://open.workbuddy.cn/en/docs/skill
