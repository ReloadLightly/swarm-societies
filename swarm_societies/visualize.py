"""Render published evidence and replay recorded episodes; never run evolution.

Usage: python -m swarm_societies.visualize --summary evidence/experiment/summary.json
       --replay evidence/experiment/replay.json --output figures
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import tempfile
import textwrap
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "swarm-societies-matplotlib"))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import PillowWriter
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch

BACKGROUND = "#FFFEFC"
INK = "#161625"
SECONDARY = "#6F6A78"
RULE = "#DCD7E0"
MUTED = "#F1EEF3"
COLORS = ["#3534CF", "#C93683", "#F26A37", "#36877D", "#8670AC", "#A78066"]
STYLE = "Swarm Societies / Chromatic Field"


def society_color(sid: int) -> str:
    return COLORS[int(sid) % len(COLORS)]


def theme() -> None:
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 11,
        "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlepad": 12,
        "axes.labelsize": 11, "xtick.labelsize": 10, "ytick.labelsize": 10,
        "legend.fontsize": 10, "legend.frameon": False,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.linewidth": 0.65, "axes.edgecolor": RULE,
        "axes.labelcolor": INK, "text.color": INK,
        "xtick.color": SECONDARY, "ytick.color": SECONDARY,
        "grid.color": RULE, "grid.linewidth": 0.65,
        "figure.facecolor": BACKGROUND, "axes.facecolor": BACKGROUND,
        "savefig.facecolor": BACKGROUND, "savefig.dpi": 180,
        "svg.fonttype": "none", "svg.hashsalt": "swarm-societies-v1",
        "pdf.fonttype": 42,
    })


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(fig, stem: Path, *, close: bool = True) -> list[Path]:
    stem.parent.mkdir(parents=True, exist_ok=True)
    files = []
    for ext in ("svg", "pdf", "png"):
        metadata = {"Creator": STYLE}
        if ext == "svg":
            metadata["Date"] = None
        if ext == "pdf":
            metadata.update(CreationDate=None, ModDate=None)
        target = stem.with_suffix("." + ext)
        fig.savefig(target, bbox_inches="tight", pad_inches=.18,
                    facecolor=BACKGROUND, metadata=metadata)
        files.append(target)
    if close:
        plt.close(fig)
    return files


def number(value, places=2) -> str:
    if isinstance(value, dict):
        value = value.get("mean")
    if value is None:
        return "—"
    try:
        return f"{float(value):.{places}f}" if math.isfinite(float(value)) else "—"
    except (TypeError, ValueError):
        return str(value)


def value(row, key, default=None):
    v = row.get(key, row.get("metrics", {}).get(key, default))
    return v.get("mean", default) if isinstance(v, dict) else v


def normalized_gain(row):
    """The trusted evaluator defines score = 1 + normalized matched gain."""
    if not row.get("valid",True):
        return None
    score=value(row,"score")
    return score-1 if score is not None else None


def title(fig, heading, subheading):
    fig.text(.07, .95, heading, fontsize=16, fontweight="bold", va="top")
    fig.text(.07, .885, subheading, fontsize=10, color=SECONDARY, va="top")


def results_table(summary, output):
    rows = summary.get("results", [])
    columns = [("Condition", "label"), ("Cases", "n"),
               ("Before\ndisturbance", "pre_welfare"),
               ("After\ndisturbance", "post_welfare"),
               ("Individual\nutility", "individual_utility"),
               ("Other societies’\nwelfare", "other_welfare")]
    text_rows = [[str(row.get("label", "Unnamed")), str(row.get("n", "—"))]
                 + [number(value(row, key),4 if "welfare" in key else 2) for _, key in columns[2:]] for row in rows]
    fig, ax = plt.subplots(figsize=(11.5, max(3.7, 2.45 + .48 * len(rows))))
    ax.set_axis_off()
    title(fig, "Collective outcomes on fresh cases", "Recorded means · common environment cases and partner/opponent snapshots")
    if text_rows:
        table = ax.table(cellText=text_rows, colLabels=[c[0] for c in columns],
                         cellLoc="right", colLoc="right", colWidths=[.28,.07,.16,.16,.16,.17],
                         bbox=[0, .06, 1, .84])
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        for (row, col), cell in table.get_celld().items():
            cell.visible_edges = "B"
            cell.set_edgecolor(RULE)
            cell.set_linewidth(.6)
            cell.set_facecolor(BACKGROUND)
            cell.PAD = .12
            if col == 0:
                cell.set_text_props(ha="left")
            if row == 0:
                cell.set_text_props(weight="bold", color=SECONDARY)
                cell.set_height(cell.get_height() * 1.6)
    else:
        ax.text(.5, .5, "No fresh-case evaluations recorded", ha="center", color=SECONDARY)
    note = summary.get("evaluation_note", "Cases measure environmental variation; independent evolutionary runs are the replication unit.")
    fig.text(.07, .065, textwrap.fill(note, 125), fontsize=9, color=SECONDARY)
    fig.subplots_adjust(left=.07, right=.96, top=.77, bottom=.20)
    paths = save(fig, output / "results-table")
    all_columns = columns + [("Within cooperation", "within_cooperation"),
        ("Between cooperation", "between_cooperation"), ("Between conflict", "between_conflict")]
    with (output / "results.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[key for _, key in all_columns])
        writer.writeheader()
        for row in rows:
            writer.writerow({key: value(row, key) for _, key in all_columns})
    lines = ["| " + " | ".join(label.replace("\n", " ") for label, _ in all_columns) + " |",
             "|:--|" + "--:|" * (len(all_columns)-1)]
    for row in rows:
        lines.append("| " + " | ".join(str(value(row, key, "—")) if key in ("label", "n")
            else number(value(row, key),4 if "welfare" in key else 2) for _, key in all_columns) + " |")
    lines += ["", note, ""]
    (output / "results-table.md").write_text("\n".join(lines))
    return paths + [output / "results.csv", output / "results-table.md"]


def evolution_plot(summary, output):
    history = summary.get("search_history", [])
    fig, ax = plt.subplots(figsize=(10, 5.4))
    title(fig, "Evolutionary search performance", "Search fitness only · candidate evaluations are not independent evolutionary runs")
    valid = [h for h in history if h.get("valid", True) and value(h, "score") is not None]
    if valid:
        x = [h.get("generation", i) for i, h in enumerate(valid)]
        y = [normalized_gain(h) for h in valid]
        kinds=sorted({h.get("kind","candidate") for h in valid})
        shapes={"member":"o","institution":"s","initial":"^","candidate":"o"}
        for kind in kinds:
            subset=[(i,h) for i,h in enumerate(valid) if h.get("kind","candidate")==kind]
            ax.scatter([x[i] for i,h in subset],[y[i] for i,h in subset],
                c=[society_color(h.get("society",h.get("society_id",0))) for i,h in subset],
                marker=shapes.get(kind,"o"),alpha=.65,s=38,label=kind.capitalize()+" evaluation",zorder=3)
        # Objectives and partner ecologies differ across proposals, so points
        # remain unconnected instead of suggesting a population learning curve.
        handles=[Line2D([],[],linestyle="",marker=shapes.get(kind,"o"),color=SECONDARY,
                 label=kind.capitalize()+" evaluation") for kind in kinds]
        retained = [h for h in valid if h.get("accepted", False)]
        if retained:
            ax.scatter([h.get("generation", history.index(h)) for h in retained],
                       [normalized_gain(h) for h in retained], marker="D", s=48,
                       facecolors="none", edgecolors=INK, label="Retained update", zorder=4)
            handles.append(Line2D([],[],linestyle="",marker="D",markerfacecolor="none",color=INK,label="Retained update"))
        missing_labels=set()
        for h in history:
            if not h.get("valid", True):
                missing_label="Evaluation infrastructure failure" if h.get("kind")=="infrastructure failure" else "Invalid candidate program"
                c,ls=(SECONDARY,"--") if h.get("kind")=="infrastructure failure" else (COLORS[2],":")
                ax.axvline(h.get("generation", history.index(h)), color=c,
                           linewidth=.8, alpha=.65,linestyle=ls,
                           label=missing_label if missing_label not in missing_labels else None)
                if missing_label not in missing_labels:
                    handles.append(Line2D([],[],color=c,linestyle=ls,linewidth=.8,label=missing_label))
                missing_labels.add(missing_label)
        ax.legend(handles=handles,loc="best")
        for i,sid in enumerate(sorted({h.get("society",h.get("society_id",0)) for h in valid})):
            ax.text(i*.17,1.035,f"Society {sid}",color=society_color(sid),fontsize=9,
                    weight="bold",transform=ax.transAxes)
        ax.set_xlabel("Evaluated evolutionary generation")
        ax.axhline(0, color=SECONDARY, linewidth=.7, linestyle="--", alpha=.6)
        ax.set_ylabel(summary.get("search_score_label", "Normalized matched fitness gain"))
        ax.grid(axis="y", alpha=.65)
        all_x=[h.get("generation",i) for i,h in enumerate(history)]
        if len(set(all_x)) == 1:
            ax.set_xlim(all_x[0]-.7, all_x[0]+.7)
            ax.set_xticks([all_x[0]])
        else:
            ax.set_xlim(min(all_x)-.3,max(all_x)+.3)
            from matplotlib.ticker import MaxNLocator
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    else:
        ax.set_axis_off()
        ax.text(.5, .58, "No evolutionary candidate evaluations recorded", ha="center", fontsize=13,
                fontweight="bold", transform=ax.transAxes)
        ax.text(.5, .38, textwrap.fill(summary.get("search_message", "Evolutionary performance is unavailable; no curve is inferred."), 80),
                ha="center", va="center", fontsize=11, color=SECONDARY, transform=ax.transAxes)
    fig.text(.07, .065, "Partner snapshots may change between generations. Color identifies the target society. Fresh-case outcomes are separate.",
             fontsize=9, color=SECONDARY)
    fig.subplots_adjust(left=.12, right=.95, top=.77, bottom=.22)
    return save(fig, output / "evolution-performance")


def lineage_plot(summary, output):
    nodes = summary.get("lineage", [])
    if len({str(n["id"]) for n in nodes}) != len(nodes):
        raise ValueError("Lineage node IDs must be unique; genotype hashes alone can recur across evaluations")
    for suffix in ("svg","pdf","png"):
        for old in output.glob(f"program-lineages-page-*.{suffix}"):
            old.unlink()
    nodes = sorted(nodes, key=lambda n: (n.get("generation",0),str(n["id"])))
    roots = [n for n in nodes if not (n.get("parent_id") or n.get("parent_ids"))]
    recent = nodes[-12:]
    selected = [n for n in roots if n not in recent] + recent
    paths = _lineage_panel(selected, output/"program-lineages",
        f"{len(nodes)} recorded programs · initial roots and latest 12 nodes shown" if len(nodes)>12
        else f"{len(nodes)} recorded programs · all available nodes shown")
    if len(nodes)>12:
        for page,start in enumerate(range(0,len(nodes),12),1):
            paths += _lineage_panel(nodes[start:start+12],output/f"program-lineages-page-{page:02d}",
                f"Full lineage · page {page}/{math.ceil(len(nodes)/12)} · off-page parents are named inside boxes")
    return paths


def _lineage_panel(nodes, destination, subtitle):
    by_id={str(n["id"]):n for n in nodes}
    def depth(node,seen=None):
        seen=set() if seen is None else seen
        parent=str(node.get("parent_id"))
        if parent not in by_id or parent in seen:
            return 0
        return 1+depth(by_id[parent],seen|{parent})
    levels=defaultdict(list)
    for node in nodes:levels[depth(node)].append(node)
    if max((len(group) for group in levels.values()),default=0)>3:
        levels=defaultdict(list)
        for i,node in enumerate(nodes):levels[i//3].append(node)
    nrows=max(levels,default=0)+1
    fig,ax=plt.subplots(figsize=(11.5,max(5.0,2.15+nrows*1.55)))
    title(fig,"Program inheritance and evaluated outcomes",subtitle)
    ax.set_axis_off()
    positions={str(node["id"]):(((3-len(group))/2+i)*3.35,(nrows-level-1)*2.0)
               for level,group in levels.items() for i,node in enumerate(group)}
    for node in nodes:
        q=positions[str(node["id"])]
        parent=node.get("parent_id")
        if parent is not None and str(parent) in positions:
            p=positions[str(parent)]
            ax.add_patch(FancyArrowPatch((p[0]+1.4,p[1]-.10),(q[0]+1.1,q[1]+1.40),
                arrowstyle="-|>",mutation_scale=11,linewidth=1.0,color=SECONDARY,alpha=.8,zorder=1))
        prior=node.get("ecological_predecessor_id")
        if prior is not None and prior!=parent and str(prior)!=str(node["id"]):
            prior_node=by_id.get(str(prior))
            prior_label=(f"S{prior_node.get('society',0)} seed" if str(prior).startswith("seed-")
                         else f"G{prior_node['generation']}") if prior_node else str(prior)[:8]
            ax.text(q[0]+2.35,q[1]+1.77,f"prior {prior_label}",ha="center",va="bottom",
                    fontsize=7.5,color=COLORS[2])
            ax.add_patch(FancyArrowPatch((q[0]+2.35,q[1]+1.74),(q[0]+2.35,q[1]+1.40),
                arrowstyle="-|>",mutation_scale=9,linewidth=.9,color=COLORS[2],linestyle="--",zorder=1))
    for node in nodes:
        x,y=positions[str(node["id"])]
        c=society_color(node.get("society",node.get("society_id",0)))
        ax.add_patch(FancyBboxPatch((x,y),2.8,1.29,boxstyle="round,pad=.1,rounding_size=.08",
            linewidth=1.15 if node.get("accepted") else .75,edgecolor=c,facecolor=BACKGROUND,zorder=2))
        label=str(node.get("label",node["id"]))
        ax.text(x+.07,y+1.13,textwrap.shorten(label,width=31,placeholder="…"),fontsize=10,weight="bold",va="top",zorder=3)
        raw_kind=str(node.get("kind","initial")).split(" · ")[0]
        status=("not evaluated" if raw_kind=="infrastructure failure" else
                "invalid program" if not node.get("valid",True) else
                "retained" if node.get("accepted") else ("rejected" if node.get("parent_id") else "root"))
        unit=f"member {node.get('target_member','?')}" if raw_kind=="member" else raw_kind
        kind=f"g{node.get('generation',0):02d} · {unit} · {status}"
        ax.text(x+.07,y+.78,textwrap.shorten(kind,width=44,placeholder="…"),fontsize=8.5,color=SECONDARY,zorder=3)
        score=normalized_gain(node)
        outcome=(f"Matched gain {number(score,4)}" if score is not None else
                 "No matched comparison" if raw_kind=="initial" else "No ecological result")
        ax.text(x+.07,y+.55,outcome,fontsize=9,zorder=3)
        change=node.get("changes") or "No inherited changes"
        if isinstance(change,list):change=", ".join(change)
        ax.text(x+.07,y+.31,textwrap.shorten(str(change),width=48,placeholder="…"),fontsize=8.0,color=SECONDARY,zorder=3)
        donor=str(node.get("parent_id") or "—")[:8]
        prior=str(node.get("ecological_predecessor_id") or "—")[:8]
        ax.text(x+.07,y+.08,f"ID {str(node['id'])[:8]} · donor {donor} · prior {prior}",fontsize=7,color=SECONDARY,zorder=3)
    if nodes:
        ax.set_xlim(-.2,9.75);ax.set_ylim(-.30,(nrows-1)*2.0+1.95)
    else:
        ax.text(.5,.55,"No inherited program changes recorded",ha="center",fontsize=13,weight="bold",transform=ax.transAxes)
    fig.text(.07,.073,"Solid arrows: proposal donor. Named dashed links: comparison incumbent when different. Borders identify societies.",fontsize=9,color=SECONDARY)
    fig.text(.07,.040,"Matched gains use the candidate’s own comparison cases. Inheritance does not establish the causal effect of an individual change.",fontsize=8.5,color=SECONDARY)
    fig.subplots_adjust(left=.07,right=.96,top=.79,bottom=.13)
    return save(fig,destination)


def cooperation_plot(summary, output):
    rows = summary.get("results", [])
    metrics = [("within_cooperation", "Within-society pooling"),
               ("between_cooperation", "Between-society aid"),
               ("between_conflict", "Between-society conflict")]
    fig, axes = plt.subplots(1,3,figsize=(11.5,5))
    title(fig,"Cooperation and conflict remain distinct","Fresh-case episode totals · pooling includes voluntary contributions and compulsory tax")
    for ax, (key,label) in zip(axes,metrics):
        xs = [i for i,r in enumerate(rows) if value(r,key) is not None]
        measures=[value(rows[i],key) for i in xs]
        ax.barh(xs,measures,color=SECONDARY,height=.48)
        xmax=max(measures,default=0) or 1
        ax.set_xlim(0,xmax*1.4)
        for i,measure in zip(xs,measures):
            ax.text(measure+xmax*.04,i,number(measure),va="center",fontsize=8.5,color=SECONDARY)
        ax.set_yticks(range(len(rows)),[r.get("short_label",r["label"]) for r in rows] if ax is axes[0] else [])
        ax.invert_yaxis()
        ax.set_title(label,fontsize=10)
        ax.grid(axis="x",alpha=.6)
        ax.set_axisbelow(True)
        ax.set_xlabel("Material units per episode")
        if not xs:
            ax.text(.5,.5,"Not recorded",ha="center",transform=ax.transAxes,color=SECONDARY)
    fig.subplots_adjust(left=.25,right=.95,top=.73,bottom=.16,wspace=.23)
    return save(fig,output/"cooperation-conflict")


def welfare_decomposition(summary, output):
    rows=summary.get("results",[])
    keys=("post_shortfall","post_infrastructure")
    if not rows or not all(value(r,k) is not None for r in rows for k in keys):
        return []
    fig,axes=plt.subplots(1,2,figsize=(11.5,max(4.7,3.1+.4*len(rows))))
    title(fig,"Material outcomes behind the welfare score",
          "Fresh-case means after the disturbance · the same focal societies and cases in both panels")
    titles=("Unmet consumption needs","Infrastructure contributing to welfare")
    labels=("Total post-disturbance shortfall", "Post-disturbance mean infrastructure")
    for ax,key,panel_heading,xlabel in zip(axes,keys,titles,labels):
        measures=[value(r,key) for r in rows]
        ax.barh(range(len(rows)),measures,height=.38,color=SECONDARY)
        xmax=max(measures) or 1
        ax.set_xlim(0,1.32*xmax)
        ax.set_yticks(range(len(rows)),[r.get("short_label",r["label"]) for r in rows] if ax is axes[0] else [])
        ax.invert_yaxis();ax.set_axisbelow(True);ax.grid(axis="x",alpha=.55)
        ax.set_title(panel_heading,fontsize=10);ax.set_xlabel(xlabel,fontsize=10)
        for i,m in enumerate(measures):
            ax.text(m+.035*xmax,i,number(m,3),va="center",fontsize=9,color=SECONDARY)
    fig.text(.07,.095,"Welfare = (consumption − 0.5 × shortfall) / (members × phase ticks) + 0.03 × mean infrastructure.",
             fontsize=9,color=SECONDARY)
    fig.text(.07,.045,"An infrastructure bonus can offset unmet consumption in this score; a higher score alone does not establish adaptation.",
             fontsize=9,color=SECONDARY)
    fig.subplots_adjust(left=.28,right=.96,top=.72,bottom=.29,wspace=.26)
    return save(fig,output/"welfare-decomposition")


def positions_for(frame):
    societies = frame["societies"]
    centers, patches, members = {}, {}, {}
    n = len(societies)
    for j,s in enumerate(societies):
        angle = math.pi/2 + 2*math.pi*j/n
        unit = np.array([math.cos(angle),math.sin(angle)])
        centers[s["id"]] = unit*2.15
        patches[j] = unit*.83
        for k,m in enumerate(s["members"]):
            a = 2*math.pi*k/len(s["members"])
            members[(s["id"],m["id"])] = centers[s["id"]] + .59*np.array([math.cos(a),math.sin(a)])
    return centers,patches,members


def replay_frame(fig, frame, config, population_label="Recorded population"):
    fig.clear()
    ax = fig.add_axes([.025,.13,.64,.73])
    side = fig.add_axes([.69,.12,.29,.73])
    ax.set_aspect("equal"); ax.set_axis_off(); side.set_axis_off()
    ax.set_xlim(-3.1,3.1); ax.set_ylim(-3.0,3.1)
    tick = frame["tick"]
    disturbed = frame.get("disturbed",tick >= config.get("disturbance_tick",10**9))
    fig.text(.045,.945,"A shared ecology of distinct societies",fontsize=16,weight="bold")
    fig.text(.045,.89,f"{population_label}  ·  Tick {tick:03d}  ·  {'AFTER DISTURBANCE' if disturbed else 'BEFORE DISTURBANCE'}",
             fontsize=11,color=COLORS[2] if disturbed else SECONDARY)
    centers,patches,members = positions_for(frame)
    for pid,amount in enumerate(frame.get("patches",[])):
        if isinstance(amount,dict): amount = amount.get("stock",amount.get("resources",0))
        x,y = patches[pid]
        ax.scatter([x],[y],marker="D",s=260,color=MUTED,edgecolors=RULE,zorder=3)
        ax.text(x,y,f"{amount:.0f}",ha="center",va="center",fontsize=9,zorder=4)
        ax.text(x,y-.28,f"Patch {pid}",ha="center",fontsize=8,color=SECONDARY)
    for s in frame["societies"]:
        sid=s["id"]; c=society_color(sid); center=centers[sid]
        ax.add_patch(Circle(center,.81,facecolor=c,alpha=.055,edgecolor="none",zorder=0))
        ax.scatter([center[0]],[center[1]],marker="s",s=180,facecolors=BACKGROUND,edgecolors=c,zorder=4)
        ax.text(*center,"T",ha="center",va="center",fontsize=8,color=c,zorder=5)
        ax.text(center[0],center[1]+.95,f"Society {sid}",ha="center",weight="bold",fontsize=11,color=c)
        for m in s["members"]:
            xy=members[(sid,m["id"])]; action=m.get("action","rest")
            ax.scatter([xy[0]],[xy[1]],s=180,color=c,edgecolors=BACKGROUND,linewidth=.9,zorder=6)
            symbol = {"rest":"·"}.get(action,action[:1].upper())
            ax.text(*xy,symbol,ha="center",va="center",fontsize=8,color="white",weight="bold",zorder=7)
        total_wealth=sum(m.get("wealth",0) for m in s["members"])
        y=.98-list(centers).index(sid)*.22
        side.text(0,y,f"Society {sid}",color=c,fontsize=12,weight="bold",va="top")
        side.text(0,y-.055,f"Private wealth    {total_wealth:8.1f}\nTreasury          {s.get('treasury',0):8.1f}\nInfrastructure    {s.get('infrastructure',0):8.1f}",
                  family="DejaVu Sans Mono",fontsize=9,va="top",linespacing=1.7)
    totals=defaultdict(float)
    for event in frame.get("events",[]):
        kind=event.get("kind",""); amount=float(event.get("amount",0)); totals[kind]+=amount
        sid=event.get("society"); mid=event.get("member")
        start=members.get((sid,mid),centers.get(sid))
        end=None; color=society_color(sid or 0); linestyle="-"
        if kind=="harvest":
            target=event.get("patch",event.get("target_patch"))
            if target is None:
                actor=next((m for s in frame["societies"] if s["id"]==sid for m in s["members"] if m["id"]==mid),{})
                target=actor.get("patch",actor.get("target",sid))
            start,end=patches.get(target),start
        elif kind in ("contribute","tax"):
            end=centers.get(sid)
        elif kind=="redistribute":
            end=start; start=centers.get(sid)
        elif kind in ("raid","share"):
            end=members.get((event.get("target_society"),event.get("target_member")),centers.get(event.get("target_society")))
            if kind=="raid":
                start,end=end,start  # Stolen resources move from the victim to the raider.
                linestyle="--"
        if start is not None and end is not None and amount>0 and np.linalg.norm(np.array(start)-end)>.05:
            ax.add_patch(FancyArrowPatch(start,end,arrowstyle="-|>",mutation_scale=8,
                linewidth=min(2.2,.55+math.sqrt(amount)*.17),color=color,alpha=.55,
                linestyle=linestyle,connectionstyle="arc3,rad=.10",shrinkA=7,shrinkB=7,zorder=2))
    flow="  ·  ".join(f"{k} {v:.1f}" for k,v in sorted(totals.items()) if v>0)
    fig.text(.045,.085,textwrap.shorten("Material flows this tick: "+(flow or "none recorded"),width=140,placeholder="…"),fontsize=9,color=SECONDARY)
    fig.text(.045,.045,"Member actions: H harvest · C contribute · S share · R raid · G guard · dot rest. T = treasury; diamonds = patch stock.",fontsize=8.5,color=SECONDARY)
    fig.text(.045,.015,"Arrows follow resource transfers; dashed arrows carry stolen resources toward the raider. Society layout is schematic.",fontsize=8.5,color=SECONDARY)


def render_replay(replay, output, max_frames=100):
    frames = replay.get("replay", replay.get("frames", [])) if isinstance(replay,dict) else replay
    if not frames:
        raise ValueError("Replay has no recorded frames; a synthetic animation would be misleading")
    config=replay.get("config",{}) if isinstance(replay,dict) else {}
    population_label=replay.get("population_label","Recorded population") if isinstance(replay,dict) else "Recorded population"
    fig=plt.figure(figsize=(11,6.6))
    # The static illustration is the last recorded frame, never a best-looking frame.
    replay_frame(fig,frames[-1],config,population_label)
    paths=save(fig,output/"ecology-replay",close=False)
    indexes=set(np.linspace(0,len(frames)-1,min(len(frames),max_frames),dtype=int).tolist())
    disturbance=config.get("disturbance_tick")
    indexes.update(i for i,f in enumerate(frames) if f["tick"] in (disturbance, (disturbance or 0)-1))
    writer=PillowWriter(fps=6,metadata={"title":"Recorded society ecology", "artist":STYLE})
    target=output/"ecology-replay.gif"
    with writer.saving(fig,str(target),dpi=90):
        for idx in sorted(indexes):
            replay_frame(fig,frames[idx],config,population_label)
            writer.grab_frame(facecolor=BACKGROUND)
    plt.close(fig)
    paths.append(target)
    return paths, {"total_recorded_frames":len(frames),"gif_frame_indices":sorted(indexes),
        "static_frame_tick":frames[-1]["tick"], "fps":6,"population_label":population_label,
        "geometry":"schematic society circles; no spatial movement is inferred"}


def disturbance_plot(replay, output):
    rows=replay.get("timeseries",[]) if isinstance(replay,dict) else []
    if not rows:
        return []
    fig,axes=plt.subplots(1,2,figsize=(11.5,5.4))
    title(fig,"Society trajectories through the disturbance",
          f"{replay.get('population_label','Recorded population')} · one recorded episode, not a fresh-case mean")
    for ax,key,label in zip(axes,("welfare","mean_wealth"),("Society welfare per tick","Mean private wealth")):
        for sid in sorted({r["society"] for r in rows}):
            sr=sorted([r for r in rows if r["society"]==sid],key=lambda r:r["tick"])
            ax.plot([r["tick"] for r in sr],[r[key] for r in sr],color=society_color(sid),
                    linewidth=1.4,label=f"Society {sid}")
        dt=replay.get("config",{}).get("disturbance_tick")
        if dt is not None:
            ax.axvline(dt,color=SECONDARY,linewidth=1,linestyle="--")
            ax.text(dt,.97,"Disturbance",transform=ax.get_xaxis_transform(),ha="left",va="top",fontsize=9,color=SECONDARY)
        ax.set_xlabel("Episode tick");ax.set_ylabel(label);ax.grid(axis="y",alpha=.6)
    axes[0].legend(loc="best",fontsize=9)
    fig.text(.07,.055,"All societies share the same environment; program identities and case seed are preserved with the replay.",fontsize=9,color=SECONDARY)
    fig.subplots_adjust(left=.09,right=.96,top=.76,bottom=.21,wspace=.32)
    return save(fig,output/"disturbance-response")


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary",type=Path,default=Path("evidence/experiment/summary.json"))
    parser.add_argument("--replay",type=Path)
    parser.add_argument("--output",type=Path,default=Path("figures"))
    parser.add_argument("--max-frames",type=int,default=100)
    args=parser.parse_args(argv)
    theme(); args.output.mkdir(parents=True,exist_ok=True)
    summary_bytes=args.summary.read_bytes()
    summary=json.loads(summary_bytes)
    paths=[]
    for renderer in (results_table,evolution_plot,lineage_plot,cooperation_plot,welfare_decomposition):
        paths.extend(renderer(summary,args.output))
    sources={str(args.summary):hashlib.sha256(summary_bytes).hexdigest(),"swarm_societies/visualize.py":digest(Path(__file__))}
    replay_info=None
    if args.replay:
        replay_bytes=args.replay.read_bytes()
        replay=json.loads(replay_bytes)
        replay.setdefault("population_label",summary.get("replay_label","Initial population" if summary.get("status")=="running" else "Final population"))
        replay_paths,replay_info=render_replay(replay,args.output,args.max_frames)
        paths.extend(replay_paths);paths.extend(disturbance_plot(replay,args.output))
        sources[str(args.replay)]=hashlib.sha256(replay_bytes).hexdigest()
    captions={
        "results-table":"Fresh evaluation means on common environment seeds and partner/opponent snapshots. Each row is a recorded program condition. Cases are not independent evolutionary runs. Welfare before and after the disturbance, individual utility, and other societies’ welfare remain distinct. Missing values are displayed as em dashes.",
        "evolution-performance":"Recorded search scores minus one: (candidate objective − incumbent objective) / max(1, |incumbent objective|). Each point is an evaluated candidate; outlined diamonds denote retained updates. Member objectives are private utility; institution objectives are society welfare. Fitness can change with partner composition. No observations, trajectories, descendants, uncertainty bands, or global best curves are fabricated when absent.",
        "program-lineages":"Each box is a recorded program with its normalized matched search gain, scheduled update unit, retention status, and changed source components. Component changes compare the full proposal to its source donor; only the scheduled member or institution unit enters the ecology when retained. Solid arrows connect proposal donors; named dashed orange links reference ecological comparison incumbents when different from the donor. Nodes are arranged by source ancestry, not evenly spaced generation time. Only retained candidates replace incumbents. The overview shows initial roots and the latest 12 nodes by generation, without selecting on fitness; additional numbered pages preserve all nodes in chronological groups of 12. Off-page parent IDs remain inside each box. Disconnected roots are initial programs or fixed references. Ancestry does not identify a causal contribution of a code change. Full IDs and change descriptions remain in the source JSON.",
        "cooperation-conflict":"Fresh-case means of cumulative material units across the complete episode (60 ticks in the first run), not per-tick rates. Within-society pooling equals voluntary contributions plus compulsory taxes and must not be interpreted as exclusively voluntary cooperation. Between-society aid measures material transfers to other societies. Between-society conflict measures material harm imposed on other societies. These outcomes remain distinct.",
        "welfare-decomposition":"Post-disturbance means on the same fresh cases as the results table. Left: total consumption shortfall per focal society during the post-disturbance phase; lower means fewer unmet needs. Right: mean infrastructure stock during that phase. The welfare formula is (phase consumption − 0.5 × phase shortfall) / (members × phase ticks) + 0.03 × mean infrastructure. Infrastructure therefore adds an explicit bonus: increasing it can raise welfare even when consumption shortfall worsens. These primitive outcomes must be considered separately when interpreting adaptation. No independent evolutionary-run uncertainty is available from a single search run.",
        "ecology-replay":"A recorded episode, using stable society colors. Circles represent members and their current action, squares treasuries, diamonds resource patches; directed arrows show material flows. Society layout is schematic, not simulated physical movement. The static panel is the last recorded frame. The GIF samples at most the requested frame count plus disturbance boundary frames; its exact frame indices are preserved in the manifest.",
        "disturbance-response":"The exact recorded replay episode shows society welfare and private wealth through the disturbance, indicated by a dashed vertical line. This illustration is not a population mean, a fresh-case comparison, or an independent evolutionary replicate. Lines join recorded per-tick observations; colors retain society identities.",
    }
    manifest={"schema_version":1,"style":STYLE,"sources":sources,"captions":captions,
        "replay":replay_info,"software":{"python":platform.python_version(),"matplotlib":matplotlib.__version__,"numpy":np.__version__},
        "training_performed":False,"evaluation_performed":False,
        "artifacts":{str(p.name):digest(p) for p in paths}}
    (args.output/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    readme=["# Recorded experiment figures","", "Figures are rendered from saved evidence. Rendering performs no search or evaluation.","",
        "Visual tokens follow the inspected [reference](../docs/visual-reference.md). Source and output hashes are in `manifest.json`.",""]
    for name,caption in captions.items():
        if (args.output/f"{name}.svg").exists():
            links=f"[SVG]({name}.svg) · [PDF]({name}.pdf) · [PNG]({name}.png)"
            if name=="ecology-replay":links+=" · [Animation](ecology-replay.gif)"
            if name=="results-table":links+=" · [Markdown](results-table.md) · [CSV](results.csv)"
            readme.extend([f"## {name}","",links,"",caption,""])
    pages=sorted(args.output.glob("program-lineages-page-*.svg"))
    if pages:
        readme.extend(["## Complete lineage pages","",*[
            f"- [Page {i} SVG]({p.name}) · [PDF]({p.with_suffix('.pdf').name})" for i,p in enumerate(pages,1)],""])
    (args.output/"README.md").write_text("\n".join(readme))
    print(json.dumps({"figures":len(paths),"output":str(args.output),"replay":replay_info},indent=2))


if __name__ == "__main__":
    main()
