(() => {
  function setupSite(){
    const toggle=document.getElementById('menu-toggle');
    const links=document.getElementById('nav-links');
    if(toggle&&links){
      toggle.addEventListener('click',()=>{
        const open=links.classList.toggle('is-open');
        toggle.setAttribute('aria-expanded',String(open));
      });
      links.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>{
        links.classList.remove('is-open');
        toggle.setAttribute('aria-expanded','false');
      }));
    }

    const items=[...document.querySelectorAll('.fade-in')];
    if('IntersectionObserver' in window){
      const obs=new IntersectionObserver(entries=>entries.forEach(e=>{
        if(e.isIntersecting){
          e.target.classList.add('is-visible');
          obs.unobserve(e.target);
        }
      }),{threshold:.12});
      items.forEach(x=>obs.observe(x));
    }else{
      items.forEach(x=>x.classList.add('is-visible'));
    }

    const sections=[...document.querySelectorAll('[data-section]')];
    const nav=[...document.querySelectorAll('.nav__link')];
    if('IntersectionObserver' in window){
      const active=new IntersectionObserver(entries=>{
        const visible=entries.filter(e=>e.isIntersecting).sort((a,b)=>b.intersectionRatio-a.intersectionRatio);
        if(!visible.length)return;
        const id=visible[0].target.id;
        nav.forEach(a=>a.classList.toggle('is-active',a.getAttribute('href')==='#'+id));
      },{rootMargin:'-30% 0px -55% 0px',threshold:[.05,.25,.5]});
      sections.forEach(s=>active.observe(s));
    }

    const style=document.createElement('link');
    style.rel='stylesheet';
    style.href='project-mundial.css?v=20260721-2205';
    document.head.appendChild(style);

    const projectScript=document.createElement('script');
    projectScript.src='project-mundial.js?v=20260721-2205';
    projectScript.defer=true;
    document.body.appendChild(projectScript);
  }

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',setupSite);
  }else{
    setupSite();
  }
})();
