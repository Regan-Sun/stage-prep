# 运行与数据约定

版本：1.0.0。脚本的 JSON `schema_version` 为 `1.0`。

## 平台无关运行

命令中的 `python` 表示当前环境实际可用的 Python 3.10+，`<skill>` 表示本 Skill 的实际目录，`<run>` 表示用户本轮输出目录。不要原样执行占位符。

报告生成只需 Python 标准库。视频检查和抽帧需要 `opencv-python-headless`；联络表需要 Pillow（可选）；音频导出需要 PATH 中的 ffmpeg（可选）；ffprobe 可提供更准确的媒体元数据。可先运行 `python -c "import cv2; print(cv2.__version__)"` 检查。安装依赖时使用用户允许的环境，优先隔离依赖；不要写死开发机器的路径。

也支持安装目录下的 `.runtime` 隔离依赖，检查和抽帧脚本会自动加载。经用户授权后可使用 `python -m pip install --target <skill>/.runtime opencv-python-headless Pillow`。此目录不进入跨平台分发包；换 Python 版本或操作系统后需重新安装，不能照搬编译依赖。

```text
python <skill>/scripts/inspect_media.py <video>
python <skill>/scripts/extract_evidence.py <video> --out <run>/evidence-01 --start 8 --end 13 --step 0.5
python <skill>/scripts/build_report.py <run>/plan-input.json --out <run>/plan-report
python <skill>/scripts/build_report.py <run>/review-input.json --out <run>/review-report
```

提取音频可加 `--audio`；WAV 从 start 开始，音频工具返回相对时间时需加 manifest 的 audio_offset_seconds。不内置转写 API、秘钥或服务承诺。可用用户字幕辅助，但必须标记来源和实际核验程度。

所有输出目录需是新目录，防止覆盖。视频本身不会改动。frames.json 记录请求时间、解码时间、帧号和图片哈希；可变帧率视频需核对字幕同步。抽帧脚本不会更新 `observed` 为 true；必须由实际查看画面的模型在复盘中记录自己观察到什么。

## plan.json

必需：schema_version、mode=plan、title、script_version、source_text、intent、assumptions、paragraphs、actions、stage、practice。

- `paragraphs`: `[{"id":"P01","text":"原稿完整段落，保留换行"}]`。拼接 text 必须逐字符等于 source_text。
- `actions`: 每条有 paragraph_id、quote（原文连续片段）、task、prepare、land、hold、reset、reason、alternative，均用中文可读文本。允许零条，不强配动作。
- `stage.orientation`: 明确观众在图下方，图左=演讲者右。
- `stage.positions`: `[{"id":"C","meaning":"当下与结尾","x":0.5,"y":0.7}]`，x/y 为0—1坐标，y越大越靠近观众。
- `stage.moves`: 每条 from/to 指向位置 ID；reason、connector、key_sentence 必填，后两者需来自原稿。无移动时为空数组。
- `practice`: focus（一个重点）、steps（字符串数组）、criterion（具体观察标准）。

## review.json

必需：schema_version、mode=review、title、scope、findings、practice。可增加 source_video、script_version、plan_reference、previous_review，使用可读来源名称，不要求他人机器上同一路径存在。

- `scope`: intervals（[[起秒,止秒]]）、viewing_method、audio_status、limitations。后面三项用真实中文说明，不能笼统声称“完整看过”。
- `findings`: 每条 title、interval、status、priority（keep/adjust/observe）、fact、interpretation、advice、dynamic（布尔）、frames。最多一条 adjust。dynamic 为 true 时需 sequence_basis，写明实际连续观察方式、覆盖范围和原视频定位，不能只列几张图就声称已看连续动作。
- `frames`: 每张 file（相对输入 JSON 的路径）、seconds、context。脚本自动复制图片到报告目录并重写 JSON 引用。
- `context`: state（speech/silence/unknown）、source（台词与时间依据）、before、after（各最多两句）；speech 必须给 current、interval，截图必须处于句区间内；silence 必须 verified_silence=true；不知道口播状态必须 unknown。
- `practice`: 与 A 相同。

当前句与前后文需人工核对。渲染器只检验结构、图片存在、时间范围和静默标记；不能自动验证台词真实或判断动作目的。不要把验证通过当作内容已审定。

只有字幕碎片而没有完整语句时，在 source 明确标记“字幕片段，未听音，非完整句”。不得把两个字幕条冒充两句；缺失的前后完整两句留空并说明。此时 speech 仅表示有文字对应证据，不表示已确认声音同步。

## 对比与可携带性

每轮使用新目录；plan/review 保留稿件版本、原始文件名称和原视频时间码。两次视频按相同语义定位，分别在对应 review 中存证据，最后并列解释同一练习指标。没有复录时只交付下一轮标准。

输出 HTML 是本地阅读版，Markdown 是可编辑版；图片相对引用。分享时带整个报告目录。公共分发包中的案例图可按可用范围删减，不影响文本规划和自有视频复盘。
