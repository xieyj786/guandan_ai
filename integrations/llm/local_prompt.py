"""Lossless, compact serialization for local benchmark requests."""
import json
import re

FAST_SYSTEM = (
    '你是掼蛋玩家，只按自己的手牌与公开信息决策，不猜未知手牌。两副牌；红心配开启时红心级牌为逢人配。'
    '动作已由引擎验证，不自行添加。优先一手走完；队友控牌默认让牌，但可直接走完或封堵报单下家。'
    '队友报单且自己牌弱、超过三手才走完时送现成小散单；有控制牌按自身计划。对手报单避免喂小单。推荐仅供参考。'
    '编码s/h/c/d=黑桃/红心/梅花/方块，X/Y=小王/大王，点数2至10及JQKA；空格分牌，重复表示多张。'
    '已出中编码=数量；近况数组=[玩家,牌张,牌型,剩余]，pass/lead为过牌/接风，finish后为名次，字符串原义。'
    '动作对象的键就是编号，空串表示过牌。只返回JSON {"action_id":整数编号}，不要解释。'
)


def encode_cards(text):
    for before, after in (('小王','X'),('大王','Y'),('♠','s'),('♥','h'),('♣','c'),('♦','d')):
        text=text.replace(before,after)
    return text


def decode_cards(text):
    for before, after in (('X','小王'),('Y','大王'),('s','♠'),('h','♥'),('c','♣'),('d','♦')):
        text=text.replace(before,after)
    return text


def encode_history(text):
    match=re.fullmatch(r'(AI\d+) 出牌：(.+) 〔([A-Z_0-9]+)〕，剩余 (\d+) 张',text)
    if match:
        player,cards,category,left=match.groups()
        return [player,encode_cards(cards.replace(', ',' ')),category,int(left)]
    for pattern,tag in ((r'(AI\d+) 过牌','pass'),(r'(AI\d+) 接风，重新领出。','lead')):
        match=re.fullmatch(pattern,text)
        if match:return [match[1],tag]
    match=re.fullmatch(r'(AI\d+) 已出完，排名第 (\d+)',text)
    if match:return [match[1],'finish',int(match[2])]
    return text


def decode_history(value):
    if isinstance(value,str):return value
    player=value[0]
    if len(value)==4:
        return f'{player} 出牌：{", ".join(decode_cards(value[1]).split())} 〔{value[2]}〕，剩余 {value[3]} 张'
    if value[1]=='pass':return f'{player} 过牌'
    if value[1]=='lead':return f'{player} 接风，重新领出。'
    return f'{player} 已出完，排名第 {value[2]}'


def fast_prompt(state, level, wildcards):
    data={'我':state['玩家'],'级牌':int(level),'红心配':wildcards,
          '手牌':encode_cards(' '.join(state['手牌'])),'队友剩余':state['队友剩余'],
          '敌下家上家剩余':state['下家和上家对手剩余'],'控牌者':state['当前控牌者'],
          '当前牌':encode_cards(' '.join(state['当前牌'])),
          '已出':' '.join(f'{encode_cards(card)}={count}' for card,count in state['公开已出牌及张数'].items()),
          '近况':[encode_history(item) for item in state['近期记录']],
          '推荐':state['规则推荐编号'],
          '动作':{str(action['id']):encode_cards(' '.join(action['cards'])) for action in state['合法动作']}}
    return FAST_SYSTEM+'\n'+json.dumps(data,ensure_ascii=False,separators=(',',':'))
