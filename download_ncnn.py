from ultralytics import YOLO

# 使用项目中已有的模型文件
model = YOLO("project/yolov8n.pt")

# 导出为 NCNN 格式
model.export(format="ncnn")

print("导出完成！生成的文件夹: yolov8n_ncnn_model")
