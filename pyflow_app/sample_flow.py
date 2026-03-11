from .models import Command, TaskFlowManager


def build_sample_flow_manager() -> TaskFlowManager:
    manager = TaskFlowManager()
    manager.flow_id = "sample_flow"
    manager.flow_name = "示例流程"

    node1 = manager.add_node("get_reviews", "获取评论", "🌐")
    node1.description = "从 API 获取用户评论数据"
    node1.commands.append(Command(name="检查网络", command="echo '检查网络连接...'"))
    node1.commands.append(Command(name="获取评论", command="echo 'POST http://qdrant:6333/reviews'"))

    node2 = manager.add_node("kmeans", "K-means 聚类", "🧮")
    node2.description = "应用 K-means 算法进行聚类分析"
    node2.commands.append(Command(name="加载数据", command="echo '加载评论数据...'"))
    node2.commands.append(Command(name="执行聚类", command="echo '运行 K-means 算法...'"))

    node3 = manager.add_node("clusters_list", "转换为列表", "📋")
    node3.description = "将聚类结果转换为列表格式"
    node3.commands.append(Command(name="格式化输出", command="echo '转换聚类结果为列表...'"))

    node4 = manager.add_node("agent", "客户洞察代理", "🤖")
    node4.description = "使用 AI 代理分析客户洞察"
    node4.commands.append(Command(name="加载模型", command="echo '加载 OpenAI 模型...'"))
    node4.commands.append(Command(name="分析数据", command="echo '分析聚类数据生成洞察...'"))

    node5 = manager.add_node("gsheets", "写入表格", "📊")
    node5.description = "将洞察结果写入 Google Sheets"
    node5.commands.append(Command(name="连接表格", command="echo '连接到 Google Sheets...'"))
    node5.commands.append(Command(name="追加数据", command="echo '追加洞察数据到表格...'"))

    manager.connect_nodes("get_reviews", "kmeans")
    manager.connect_nodes("kmeans", "clusters_list")
    manager.connect_nodes("clusters_list", "agent")
    manager.connect_nodes("agent", "gsheets")
    return manager
