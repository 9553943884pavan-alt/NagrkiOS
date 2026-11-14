import {useEffect,useId,useMemo,useRef,useState,type KeyboardEvent as ReactKeyboardEvent,type ReactNode} from 'react';
import {createPortal} from 'react-dom';
import {Check,ChevronDown,Search} from 'lucide-react';

export type SelectOption={value:string;label:string;disabled?:boolean};
type SelectMenuProps={
  value:string;
  options:SelectOption[];
  onChange:(value:string)=>void;
  ariaLabel:string;
  placeholder?:string;
  searchable?:boolean;
  disabled?:boolean;
  className?:string;
  leftIcon?:ReactNode;
};
type MenuPosition={left:number;top:number;width:number;above:boolean;maxHeight:number};

/** Shared, mouse- and keyboard-operable select. The list is portaled to avoid clipping by tables/cards. */
export default function SelectMenu({value,options,onChange,ariaLabel,placeholder='Choose an option',searchable=false,disabled=false,className='',leftIcon}:SelectMenuProps){
  const uid=useId().replaceAll(':','');
  const buttonRef=useRef<HTMLButtonElement>(null);
  const menuRef=useRef<HTMLDivElement>(null);
  const inputRef=useRef<HTMLInputElement>(null);
  const [open,setOpen]=useState(false);
  const [query,setQuery]=useState('');
  const [active,setActive]=useState(0);
  const [position,setPosition]=useState<MenuPosition>({left:0,top:0,width:180,above:false,maxHeight:300});
  const selected=options.find(option=>option.value===value);
  const filtered=useMemo(()=>options.filter(option=>option.label.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())),[options,query]);

  const updatePosition=()=>{
    const rect=buttonRef.current?.getBoundingClientRect();
    if(!rect)return;
    const desiredWidth=Math.max(rect.width,170);
    const width=Math.min(desiredWidth,window.innerWidth-20);
    const left=Math.min(Math.max(10,rect.left),Math.max(10,window.innerWidth-width-10));
    const predictedHeight=Math.min(filtered.length||1,7)*35+16+(searchable?55:0);
    const below=window.innerHeight-rect.bottom;
    const above=rect.top;
    const placeAbove=below<Math.min(predictedHeight,260)&&above>below;
    setPosition({left,width,above:placeAbove,top:placeAbove?Math.max(10,rect.top-8):Math.min(window.innerHeight-12,rect.bottom+7),maxHeight:Math.min(310,Math.max(80,(placeAbove?above:below)-18))});
  };

  const openMenu=()=>{
    if(disabled)return;
    setQuery('');
    const selectedIndex=options.findIndex(item=>item.value===value&&!item.disabled);
    setActive(selectedIndex>=0?selectedIndex:Math.max(0,options.findIndex(item=>!item.disabled)));
    setOpen(true);
  };
  const closeMenu=(restoreFocus=false)=>{
    setOpen(false);
    if(restoreFocus)buttonRef.current?.focus();
  };
  const choose=(option:SelectOption)=>{
    if(option.disabled)return;
    if(option.value!==value)onChange(option.value);
    closeMenu(true);
  };
  const keyHandler=(event:ReactKeyboardEvent<HTMLElement>)=>{
    if(disabled)return;
    if(event.key==='Escape'&&open){event.preventDefault();closeMenu(true);return;}
    if(event.key==='Tab'&&open){
      // The searchable menu is portaled to document.body. Preserve the expected tab order.
      const buttons=Array.from(document.querySelectorAll<HTMLElement>('a[href],button:not([disabled]),input:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])'));
      const index=buttons.indexOf(buttonRef.current!);
      const next=buttons[index+(event.shiftKey?-1:1)];
      event.preventDefault();setOpen(false);next?.focus();return;
    }
    if(event.key==='ArrowDown'||event.key==='ArrowUp'||event.key==='Home'||event.key==='End'){
      event.preventDefault();
      if(!open){openMenu();return;}
      const enabled=filtered.map((option,index)=>!option.disabled?index:-1).filter(index=>index>=0);
      if(!enabled.length)return;
      const current=enabled.indexOf(active);
      if(event.key==='Home')setActive(enabled[0]);
      else if(event.key==='End')setActive(enabled[enabled.length-1]);
      else setActive(enabled[(current+(event.key==='ArrowDown'?1:-1)+enabled.length)%enabled.length]);
      return;
    }
    if(event.key==='Enter'||event.key===' '){
      if(event.key===' '&&searchable&&event.target===inputRef.current)return;
      event.preventDefault();
      if(!open)openMenu();
      else if(filtered[active]&&!filtered[active].disabled)choose(filtered[active]);
    }
  };

  useEffect(()=>{
    if(!open)return;
    updatePosition();
    const onOutside=(event:PointerEvent)=>{
      const target=event.target as Node;
      if(!buttonRef.current?.contains(target)&&!menuRef.current?.contains(target))setOpen(false);
    };
    const onResize=()=>updatePosition();
    const onEscape=(event:KeyboardEvent)=>{if(event.key==='Escape')closeMenu(true);};
    document.addEventListener('pointerdown',onOutside);
    document.addEventListener('keydown',onEscape);
    window.addEventListener('resize',onResize);
    window.addEventListener('scroll',onResize,true);
    return()=>{
      document.removeEventListener('pointerdown',onOutside);
      document.removeEventListener('keydown',onEscape);
      window.removeEventListener('resize',onResize);
      window.removeEventListener('scroll',onResize,true);
    };
  },[open,query,filtered.length,searchable]);

  useEffect(()=>{if(open&&searchable)inputRef.current?.focus();},[open,searchable]);
  useEffect(()=>{if(!open)return;
    const node=menuRef.current?.querySelector(`[data-option-index="${active}"]`);
    node?.scrollIntoView({block:'nearest',behavior:'instant'});
  },[active,open,query]);
  useEffect(()=>{if(open){setActive(Math.max(0,filtered.findIndex(option=>!option.disabled)));}},[query]);
  useEffect(()=>{if(disabled)setOpen(false);},[disabled]);

  return <div className={`custom-select ${className}`}>
    <button ref={buttonRef} type="button" className={`custom-select-control ${open?'is-open':''}`} disabled={disabled}
      aria-label={`${ariaLabel}: ${selected?.label??placeholder}`} aria-haspopup="listbox" aria-expanded={open} aria-controls={open?`select-list-${uid}`:undefined}
      aria-activedescendant={open&&!searchable&&filtered[active]?`select-item-${uid}-${active}`:undefined}
      onClick={()=>open?closeMenu():openMenu()} onKeyDown={keyHandler}>
      {leftIcon&&<span className="custom-select-leading">{leftIcon}</span>}
      <span className="custom-select-value">{selected?.label??placeholder}</span>
      <ChevronDown size={15} className="custom-select-chevron" aria-hidden="true"/>
    </button>
    {open&&createPortal(<div ref={menuRef} id={`select-menu-${uid}`} className={`custom-select-menu ${position.above?'opens-up':''}`}
        style={{left:position.left,top:position.top,width:position.width,maxHeight:position.maxHeight,transform:position.above?'translateY(-100%)':undefined}}
        onKeyDown={keyHandler}>
      {searchable&&<div className="custom-select-search"><Search size={15}/><input ref={inputRef} type="text" role="combobox" aria-autocomplete="list" aria-expanded={open} aria-controls={`select-list-${uid}`} aria-activedescendant={filtered[active]?`select-item-${uid}-${active}`:undefined} aria-label={`Search ${ariaLabel.toLowerCase()}`} placeholder="Search options…" value={query}
        onChange={e=>{setQuery(e.target.value);setActive(0);}}/></div>}
      <div id={`select-list-${uid}`} className="custom-select-options" role="listbox" aria-label={ariaLabel}>
        {filtered.length?filtered.map((option,index)=><div key={`${option.value}-${index}`} id={`select-item-${uid}-${index}`}
          role="option" aria-selected={value===option.value} aria-disabled={option.disabled||undefined} data-option-index={index}
          className={`custom-select-option ${value===option.value?'is-selected':''} ${active===index?'is-active':''} ${option.disabled?'is-disabled':''}`}
          onPointerMove={()=>{if(!option.disabled&&active!==index)setActive(index);}}
          onClick={()=>choose(option)}>
          <span>{option.label}</span>{value===option.value&&<Check size={15} aria-hidden="true"/>}
        </div>):<div className="custom-select-no-results">No matching options</div>}
      </div>
    </div>,document.body)}
  </div>;
}
