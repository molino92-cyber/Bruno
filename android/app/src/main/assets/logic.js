/* Regras de negócio compartilhadas pelas telas do aplicativo Android. */
(function(root,factory){const api=factory();if(typeof module==='object')module.exports=api;else root.DoceLogic=api;})(globalThis,function(){
 'use strict';
 const categories=['Bolos Simples','Bolos Especiais','Cento de Brigadeiros','Kits Festa','Cupcakes','Mini Donuts','Topos de Bolo'];
 const fillings={ 'Bolos Simples':['Chocolate','Ninho','Chocolate Branco','Dois Amores'],'Bolos Especiais':['Ninho com Morango','Nutella','Ninho com Nutella','Chocolate com Morango','Doce de Leite com Ameixa']};
 const brigadeiros={Tradicional:['Chocolate','Beijinho'],Especial:['Nutella','Brigadeiro Rocher','Ninho','Ninho com Nutella'],Personalizado:['Chocolate','Beijinho','Nutella','Brigadeiro Rocher','Ninho']};
 const extras=['Massa de Chocolate','Brigadeiros no Topo','Frutas Extras','Recheios Extras','Bolo de Andar','Topo de Bolo Simples','Topo de Bolo Especial'];
 const units=['Cx','Un','Kg','Grama','Litro'];
 function ensure(value,message){if(!value)throw Error(message);}
 function today(date=new Date()){return [date.getFullYear(),String(date.getMonth()+1).padStart(2,'0'),String(date.getDate()).padStart(2,'0')].join('-');}
 function plusDays(value,days){const d=new Date(value+'T12:00:00');d.setDate(d.getDate()+days);return today(d);}
 function money(cents){return new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(cents/100);}
 function amount(value){const number=Number(String(value||0).replace(',','.'));ensure(Number.isFinite(number)&&number>=0,'Informe um valor válido, maior ou igual a zero.');return Math.round((number+Number.EPSILON)*100);}
 function price(product,on=today()){const promo=!!product.promo_enabled&&product.promo_start<=on&&product.promo_end>=on;return {value:promo?product.promo_cents:product.price_cents,promotional:promo};}
 function line(product,options){
  const qty=Number(options.quantity),isCake=!!fillings[product.category];
  ensure(Number.isFinite(qty)&&qty>0&&qty<=100000,'Informe uma quantidade válida.');
  ensure(isCake||Number.isInteger(qty),'Informe uma quantidade inteira para unidades e centos.');
  const selected=options.fillings||[],under=isCake&&qty<2,limit=qty<2?1:2,excess=isCake&&selected.length>limit;
  if(isCake){ensure(selected.length&&selected.every(f=>fillings[product.category].includes(f))&&new Set(selected).size===selected.length,'Escolha recheios válidos para o tipo de bolo.');ensure(!under||options.exception,'O mínimo padrão é 2 kg. Confirme a exceção com a confeiteira.');ensure(!excess||options.exception,`O padrão para ${qty.toString().replace('.',',')} kg é até ${limit} recheio(s). Confirme a exceção.`);ensure(!(under||excess)||(options.negotiation||'').trim(),'Registre o motivo e a condição da exceção.');}
  const kind=options.brigadeiro_type,flavors=options.flavors||[];
  if(product.category==='Cento de Brigadeiros'){
   ensure(brigadeiros[kind]&&flavors.length===(options.split?2:1)&&flavors.every(f=>brigadeiros[kind].includes(f)),'Escolha o tipo e os sabores dos brigadeiros.');
   ensure(!options.split||flavors[0]!==flavors[1],'Na divisão 50/50, escolha dois sabores diferentes.');ensure(kind!=='Personalizado'||(options.details||'').trim(),'Descreva a personalização dos brigadeiros.');
  }
  const additions=(options.extras||[]).map(e=>{
   ensure(e.name&&Number.isInteger(e.quantity)&&e.quantity>0&&Number.isSafeInteger(e.unit_cents)&&e.unit_cents>=0,'Confira a quantidade e o preço dos adicionais.');
   if(e.name==='Brigadeiros no Topo'){ensure(brigadeiros[e.brigadeiro_type]&&e.flavors?.length&&e.flavors.every(f=>brigadeiros[e.brigadeiro_type].includes(f)),'Escolha os sabores dos brigadeiros adicionais.');ensure(e.brigadeiro_type!=='Personalizado'||e.personalization?.trim(),'Descreva a personalização dos brigadeiros adicionais.');}
   return {...e,amount_cents:e.quantity*e.unit_cents};
  });
  const current=price(product);ensure(current.value>0||options.gift,'Cadastre o preço do produto ou marque como cortesia.');
  const total=Math.round(current.value*Math.round(qty*1000)/1000)+additions.filter(e=>!e.gift).reduce((sum,e)=>sum+e.amount_cents,0);
  return {product_id:product.id,name:product.name,category:product.category,description:product.description,composition:[...(product.composition||[])],quantity:qty,unit:product.unit,unit_cents:current.value,regular_unit_cents:product.price_cents,promotional:current.promotional,fillings:selected,extras:additions,flavors,brigadeiro_type:kind||'',split:!!options.split,gift:!!options.gift,details:options.details||'',reference_photo:options.reference_photo||'',negotiation:{under_minimum:under,extra_fillings:excess,notes:under||excess?options.negotiation:''},total_cents:options.gift?0:total};
 }
 function totals(lines,settings={}){
  const subtotal=lines.reduce((sum,l)=>sum+l.total_cents,0),discount=Number(settings.discount_cents||0),delivery=Number(settings.delivery_cents||0),percent=Number(settings.pix_percent||0);
  ensure([subtotal,discount,delivery].every(Number.isSafeInteger)&&discount>=0&&discount<=subtotal&&delivery>=0,'O desconto geral não pode superar o subtotal. Confira os valores.');
  ensure(Number.isFinite(percent)&&percent>=0&&percent<=100,'O desconto percentual deve ficar entre 0% e 100%.');
  ensure(!settings.pix_enabled||settings.payment_method!=='Cartão','Desative o desconto PIX para receber por cartão.');
  const pix=settings.pix_enabled?Math.round((subtotal-discount)*Math.round(percent*100)/10000):0,total=subtotal-discount+delivery-pix;
  return {subtotal_cents:subtotal,discount_cents:discount,delivery_cents:delivery,card_cents:subtotal-discount+delivery,pix_discount_cents:pix,total_cents:total,deposit_cents:Math.ceil(total/2)};
 }
 function paid(order){return (order.payments||[]).reduce((sum,p)=>sum+p.amount_cents,0);}
 function status(order,on=today()){
  if(order.delivered)return 'Entregue';const received=paid(order),t=order.totals;
  if(received>=t.total_cents&&t.total_cents>0)return 'Quitado / Data Reservada';
  if(received>=t.deposit_cents&&t.total_cents>0)return 'Aprovado / Data Reservada';
  return order.valid_until<on?'Vencido':'Em Aberto';
 }
 function payment(order,cents,method,note=''){
  ensure(!order.delivered&&status(order)!=='Vencido','Renove o orçamento vencido antes de registrar o pagamento.');
  ensure(Number.isSafeInteger(cents)&&cents>0&&cents<=order.totals.total_cents-paid(order),'Informe um recebimento positivo, sem ultrapassar o saldo.');
  ensure(['PIX','Dinheiro','Cartão'].includes(method),'Escolha a forma de pagamento.');
  return {amount_cents:cents,method,note,received_at:new Date().toISOString()};
 }
 function cpf(value){const digits=String(value||'').replace(/\D/g,'');if(!digits)return '';ensure(/^\d{11}$/.test(digits)&&new Set(digits).size>1,'CPF inválido.');for(let n=9;n<=10;n++){let sum=0;for(let i=0;i<n;i++)sum+=Number(digits[i])*(n+1-i);ensure((sum*10)%11%10===Number(digits[n]),'CPF inválido.');}return digits;}
 function customer(values){
  const c={...values};c.name=String(c.name||'').trim();ensure(c.name.length>=2,'Informe o nome completo.');c.phone=String(c.phone||'').replace(/\D/g,'');ensure(/^\d{10,13}$/.test(c.phone),'Informe o telefone com DDD.');c.cpf=cpf(c.cpf);c.email=String(c.email||'').trim().toLowerCase();ensure(!c.email||/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(c.email),'Informe um e-mail válido.');c.postal_code=String(c.postal_code||'').replace(/\D/g,'');ensure(!c.postal_code||/^\d{8}$/.test(c.postal_code),'O CEP deve ter oito dígitos.');return c;
 }
 function address(c){return [c.street&&(c.street+(c.number?', '+c.number:'')),c.complement,c.neighborhood,[c.city,c.state].filter(Boolean).join(' / '),c.postal_code?'CEP '+c.postal_code:''].filter(Boolean).join(' · ');}
 function validateBackup(state){
  ensure(state&&state.schema===1&&state.settings&&state.images,'Este arquivo não é um backup do aplicativo Android.');
  for(const key of ['products','customers','inventory','quotes']){ensure(Array.isArray(state[key])&&state[key].every(item=>item&&typeof item.id==='string'&&item.id.length<100),'Backup com cadastros inválidos.');ensure(new Set(state[key].map(x=>x.id)).size===state[key].length,'O backup possui identificadores duplicados.');}
  ensure(Object.values(state.images).every(value=>typeof value==='string'&&/^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/.test(value)&&value.length<=900000),'O backup possui uma imagem inválida.');
  for(const q of state.quotes){ensure(Array.isArray(q.lines)&&q.totals&&Number.isSafeInteger(q.totals.total_cents)&&q.totals.total_cents>0&&Array.isArray(q.payments),'Backup com orçamento inválido.');ensure(state.customers.some(c=>c.id===q.customer_id),'Backup com pedido sem cadastro de cliente.');ensure(q.payments.every(p=>Number.isSafeInteger(p.amount_cents)&&p.amount_cents>0)&&paid(q)<=q.totals.total_cents,'Backup com pagamentos inválidos.');}
  return state;
 }
 return {categories,fillings,brigadeiros,extras,units,today,plusDays,money,amount,price,line,totals,paid,status,payment,cpf,customer,address,validateBackup};
});
