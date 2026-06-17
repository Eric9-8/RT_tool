import type { GsAlignmentView } from "../types";

type BlockListProps = {
  blocks: GsAlignmentView[];
  selectedBlockId: string | null;
  onSelect: (blockId: string) => void;
};

export function BlockList(props: BlockListProps) {
  const { blocks, selectedBlockId, onSelect } = props;

  return (
    <section className="panel">
      <div className="panel-header">
        <span className="eyebrow">Block Index</span>
        <h2>GS Block 列表</h2>
      </div>
      <div className="block-list">
        {blocks.map((block) => (
          <button
            key={block.blockId}
            className={block.blockId === selectedBlockId ? "block-card active" : "block-card"}
            onClick={() => onSelect(block.blockId)}
            type="button"
          >
            <strong>Block {block.blockId}</strong>
            <span>Scale {block.scale.toFixed(3)}</span>
            <span>{block.filename ?? "No GS asset reference"}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
