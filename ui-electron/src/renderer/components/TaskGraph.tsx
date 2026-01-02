import React, { useMemo } from "react";
import dagre from "dagre";
import { PlanTask } from "../apiClient";

type Props = {
  tasks: PlanTask[];
  onTaskClick?: (taskId: string) => void;
};

type NodePosition = {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  task: PlanTask;
};

type Edge = {
  from: string;
  to: string;
  fromNode?: { x: number; y: number };
  toNode?: { x: number; y: number };
};

const NODE_WIDTH = 160;
const NODE_HEIGHT = 60;

const STATUS_COLORS: Record<string, string> = {
  done: "#4caf50",
  doing: "#ff9800",
  failed: "#f44336",
  todo: "#9e9e9e",
  canceled: "#795548"
};

export default function TaskGraph({ tasks, onTaskClick }: Props) {
  const { nodes, edges, width, height } = useMemo(() => {
    const g = new dagre.graphlib.Graph();
    g.setGraph({ rankdir: "TB", nodesep: 40, ranksep: 60 });
    g.setDefaultEdgeLabel(() => ({}));

    const taskMap = new Map<string, PlanTask>();
    const edgeList: Edge[] = [];

    tasks.forEach((task) => {
      const id = task.step_id || task.id || task.task_id || "";
      taskMap.set(id, task);
      g.setNode(id, { width: NODE_WIDTH, height: NODE_HEIGHT });
    });

    tasks.forEach((task) => {
      const id = task.step_id || task.id || task.task_id || "";
      (task.dependencies || []).forEach((dep) => {
        if (taskMap.has(dep)) {
          g.setEdge(dep, id);
          edgeList.push({ from: dep, to: id });
        }
      });
    });

    dagre.layout(g);

    const nodePositions: NodePosition[] = [];
    g.nodes().forEach((id) => {
      const node = g.node(id);
      const task = taskMap.get(id);
      if (node && task) {
        nodePositions.push({
          id,
          x: node.x - NODE_WIDTH / 2,
          y: node.y - NODE_HEIGHT / 2,
          width: NODE_WIDTH,
          height: NODE_HEIGHT,
          task
        });
      }
    });

    const graphInfo = g.graph();
    return {
      nodes: nodePositions,
      edges: edgeList.map((e) => ({
        ...e,
        fromNode: g.node(e.from),
        toNode: g.node(e.to)
      })),
      width: (graphInfo.width || 400) + 40,
      height: (graphInfo.height || 300) + 40
    };
  }, [tasks]);

  if (tasks.length === 0) {
    return <div className="muted">暂无任务数据</div>;
  }

  return (
    <div className="task-graph-container">
      <svg width={width} height={height} className="task-graph">
        <defs>
          <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="#888" />
          </marker>
        </defs>

        {edges.map((edge, idx) => {
          const from = edge.fromNode;
          const to = edge.toNode;
          if (!from || !to) return null;
          return (
            <line
              key={`${edge.from}-${edge.to}-${idx}`}
              x1={from.x}
              y1={from.y + NODE_HEIGHT / 2}
              x2={to.x}
              y2={to.y - NODE_HEIGHT / 2}
              stroke="#888"
              strokeWidth={2}
              markerEnd="url(#arrowhead)"
            />
          );
        })}

        {nodes.map((node) => {
          const status = String(node.task.status || "todo").toLowerCase();
          const color = STATUS_COLORS[status] || STATUS_COLORS.todo;
          const title = node.task.title || node.task.name || node.id;
          return (
            <g
              key={node.id}
              transform={`translate(${node.x}, ${node.y})`}
              onClick={() => onTaskClick?.(node.id)}
              style={{ cursor: onTaskClick ? "pointer" : "default" }}
            >
              <rect width={node.width} height={node.height} rx={8} fill="#fff" stroke={color} strokeWidth={3} />
              <text x={node.width / 2} y={24} textAnchor="middle" fontSize={12} fontWeight={600}>
                {title.length > 18 ? `${title.slice(0, 16)}...` : title}
              </text>
              <text x={node.width / 2} y={42} textAnchor="middle" fontSize={10} fill="#666">
                {node.id}
              </text>
            </g>
          );
        })}
      </svg>

      <div className="task-graph-legend">
        {Object.entries(STATUS_COLORS).map(([status, color]) => (
          <span key={status} className="legend-item">
            <span className="legend-dot" style={{ background: color }} />
            {status}
          </span>
        ))}
      </div>
    </div>
  );
}
