"""Build the azure-infra-design-style reference diagram (AUT-004) as draw.io XML.

Run from the repository root, then render it:
    python3 .github/skills/azure-infra-design-style/reference_diagram.py
    .venv/bin/python scripts/render_drawio_diagram.py --input .github/skills/azure-infra-design-style/reference.drawio --output .github/skills/azure-infra-design-style/reference.png

Copy the helpers (icon, boundary, card, pill, text, edge, and the hero block) to build a
control's own docs/architecture.drawio in the same style. Icon paths are relative
to the .drawio file's directory.
"""
from xml.sax.saxutils import quoteattr
I="../../../media/icons/Azure_Public_Service_Icons/Icons/"
E="../../../media/icons/Microsoft Entra architecture icons - Oct 2023/Microsoft Entra color icons SVG/"
FONT="fontFamily=Segoe UI,Helvetica Neue,Helvetica,Arial,sans-serif;fontColor=#242424;"
cells=[]; n=[0]
def nid(p): n[0]+=1; return f"{p}{n[0]}"
def v(id_, value, style, x,y,w,h):
    cells.append(f'<mxCell id="{id_}" value={quoteattr(value)} style={quoteattr(style)} vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
def icon(path,x,y,s): v(nid("i"),"",f"shape=image;image=icon:{path};imageAspect=1;aspect=fixed;",x,y,s,s)
def boundary(x,y,w,h): v(nid("b"),"","rounded=1;absoluteArcSize=1;arcSize=18;dashed=1;dashPattern=5 4;fillColor=none;strokeColor=#3B3B3B;strokeWidth=1.5;",x,y,w,h)
def card(id_,x,y,w,h,title,desc,ic,s=40):
    v(id_,f"<b>{title}</b><br><span style=\"font-size:11px\">{desc}</span>",
      "rounded=1;absoluteArcSize=1;arcSize=12;whiteSpace=wrap;html=1;fillColor=#F3F2F1;strokeColor=#D6D6D6;strokeWidth=1.5;verticalAlign=top;spacingTop="+str(s+20)+";fontSize=14;"+FONT,x,y,w,h)
    icon(ic,x+(w-s)/2,y+14,s)
def pill(id_,x,y,w,label,ic):
    v(id_,f"<b>{label}</b>","rounded=1;arcSize=50;whiteSpace=wrap;html=1;fillColor=#F3F2F1;strokeColor=none;align=left;spacingLeft=52;fontSize=13;"+FONT,x,y,w,48)
    icon(ic,x+14,y+9,30)
def text(value,x,y,w,h,style=""):
    v(nid("t"),value,"text;html=1;whiteSpace=wrap;fillColor=#FFFFFF;strokeColor=none;align=center;verticalAlign=middle;fontSize=13;"+FONT+style,x,y,w,h)
def edge(s,t,ex,ey,nx,ny,two=False):
    st=f"edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#616161;strokeWidth=1.25;endArrow=block;endFill=1;endSize=5;exitX={ex};exitY={ey};entryX={nx};entryY={ny};"
    st+= "startArrow=block;startFill=1;startSize=5;" if two else "startArrow=none;"
    cells.append(f'<mxCell id="{nid("e")}" style={quoteattr(st)} edge="1" parent="1" source="{s}" target="{t}"><mxGeometry relative="1" as="geometry"/></mxCell>')

# title above the outer boundary
icon(I+"other/10018-icon-service-Azure-A.svg",318,22,30); text("<b>Azure</b>",354,22,80,30,"align=left;fontSize=18;fillColor=none;")
boundary(60,72,1060,540)
text("Resource group (shared) · AUT-004 resources are tagged <i>control-id=AUT-004</i> and removed by cleanup",250,62,680,20)
# left column
card("mi",100,120,210,130,"Managed identity","App Configuration Data Reader<br>no stored secrets",I+"identity/10227-icon-service-Managed-Identities.svg")
card("audit",100,280,210,130,"Audit log","Log Analytics · AACAudit<br>who changed the switch",I+"monitor/00009-icon-service-Log-Analytics-Workspaces.svg")
card("switch",100,440,210,130,"Stop switch","App Configuration · Free<br>one feature flag per action",I+"integration/10219-icon-service-App-Configuration.svg")
# middle
card("app",380,280,220,130,"Support chat + ACS","App Service B1 · Entra sign-in<br>ACS checks every refund",I+"app services/10035-icon-service-App-Services.svg")
# Foundry boundary with hero header
boundary(670,140,410,430)
v("hero","<b>Microsoft Foundry</b>","rounded=1;absoluteArcSize=1;arcSize=4;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#0F6CBD;strokeWidth=2;align=left;spacingLeft=64;fontSize=15;"+FONT,765,114,220,52)
icon(I+"ai + machine learning/035746832-icon-service-AI-Foundry.svg",781,123,34)
card("agent",765,200,220,140,"Foundry Agent Service","agent aut-004-support-refunds<br>3 function tools",I+"ai + machine learning/038470523-icon-service-Foundry-Agent-Service.svg")
card("model",765,400,220,140,"Foundry Models","gpt-5 · shared deployment<br>not removed by cleanup",I+"ai + machine learning/038470614-icon-service-Foundry-Models.svg")
# outside scope
pill("ops",100,650,210,"Ops Manager",I+"identity/10230-icon-service-Users.svg")
pill("user",380,650,220,"Support operator",E+"Microsoft Entra ID color icon.svg")
text("<i>People outside Azure: the Ops Manager presses the button in Azure Portal; operators sign in with Entra ID</i>",100,708,760,22,"align=left;fontSize=12;fontColor=#424242;fillColor=none;")
# edges: caller -> callee
edge("ops","switch",0.5,0,0.5,1)
edge("user","app",0.5,0,0.5,1)
edge("app","switch",0,0.5,1,0.5)
edge("switch","audit",0.5,0,0.5,1)
edge("app","agent",1,0.5,0,0.5)
edge("agent","model",0.5,1,0.5,0)
xml='<mxfile><diagram id="ref" name="AUT-004 reference"><mxGraphModel dx="1200" dy="800" grid="0" page="0" background="#FFFFFF"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'+"".join(cells)+'</root></mxGraphModel></diagram></mxfile>'
open(".github/skills/azure-infra-design-style/reference.drawio","w").write(xml)
