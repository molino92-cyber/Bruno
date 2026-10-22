const test=require('node:test');
const assert=require('node:assert/strict');
const L=require('../app/src/main/assets/logic.js');
const simple={id:'p1',name:'Bolo Simples',category:'Bolos Simples',unit:'kg',price_cents:7500,composition:[]};
const special={...simple,id:'p2',name:'Bolo Especial',category:'Bolos Especiais',price_cents:8500};
function quote(lines=[L.line(simple,{quantity:2,fillings:['Ninho']})]){const result={lines,totals:L.totals(lines),payments:[],valid_until:L.plusDays(L.today(),7)};return result;}

test('Bolos simples e especiais: mínimo, recheios exclusivos e exceção justificada',()=>{
 for(const [product,flavors] of [[simple,['Ninho','Chocolate','Dois Amores']],[special,['Nutella','Ninho com Morango','Ninho com Nutella']]]){
  for(const quantity of [1,1.5]){
   assert.throws(()=>L.line(product,{quantity,fillings:flavors.slice(0,1)}),/mínimo/);
   assert.throws(()=>L.line(product,{quantity,fillings:flavors.slice(0,1),exception:true}),/motivo/);
   const line=L.line(product,{quantity,fillings:flavors.slice(0,2),exception:true,negotiation:'Exceção combinada pela confeiteira.'});assert.ok(line.negotiation.under_minimum);assert.ok(line.negotiation.extra_fillings);
  }
  assert.equal(L.line(product,{quantity:2,fillings:flavors.slice(0,2)}).negotiation.extra_fillings,false);
  assert.throws(()=>L.line(product,{quantity:2,fillings:flavors}),/padrão/);
 }
 assert.throws(()=>L.line(simple,{quantity:2,fillings:['Nutella']}),/válidos/);
 assert.throws(()=>L.line(special,{quantity:2,fillings:['Ninho']}),/válidos/);
});
test('Adicionais por unidade, brinde e brigadeiros no topo',()=>{
 const extra={name:'Brigadeiros no Topo',quantity:10,unit_cents:300,brigadeiro_type:'Especial',flavors:['Nutella']};
 assert.equal(L.line(simple,{quantity:2,fillings:['Ninho'],extras:[extra]}).total_cents,18000);
 assert.equal(L.line(simple,{quantity:2,fillings:['Ninho'],extras:[{...extra,gift:true}]}).total_cents,15000);
 assert.equal(L.line(simple,{quantity:2,fillings:['Ninho'],extras:[extra],gift:true}).total_cents,0);
 assert.throws(()=>L.line(simple,{quantity:2,fillings:['Ninho'],extras:[{...extra,flavors:['Beijinho']}]}),/sabores/);
});
test('Cento de brigadeiros tradicional, especial, personalizado e divisão 50/50',()=>{
 const p={id:'p3',name:'Cento',category:'Cento de Brigadeiros',unit:'cento',price_cents:12000};
 assert.equal(L.line(p,{quantity:1,brigadeiro_type:'Tradicional',flavors:['Chocolate','Beijinho'],split:true}).total_cents,12000);
 assert.throws(()=>L.line(p,{quantity:1,brigadeiro_type:'Tradicional',flavors:['Chocolate','Chocolate'],split:true}),/diferentes/);
 assert.throws(()=>L.line(p,{quantity:1,brigadeiro_type:'Personalizado',flavors:['Chocolate']}),/personalização/);
 assert.ok(L.line(p,{quantity:1,brigadeiro_type:'Personalizado',flavors:['Chocolate'],details:'Tema jardim.'}));
 assert.throws(()=>L.line(p,{quantity:1.5,brigadeiro_type:'Tradicional',flavors:['Chocolate']}),/inteira/);
});
test('Promoções não ativam PIX; desconto geral, frete e arredondamento',()=>{
 const product={...simple,promo_enabled:true,promo_cents:7000,promo_start:L.today(),promo_end:L.today()},line=L.line(product,{quantity:2,fillings:['Ninho']});
 assert.equal(L.totals([line],{pix_percent:10}).total_cents,14000);
 assert.equal(L.totals([line],{discount_cents:1000,delivery_cents:2000,pix_enabled:true,pix_percent:10}).total_cents,13700);
 assert.throws(()=>L.totals([line],{discount_cents:14001}),/desconto/);
 assert.throws(()=>L.totals([line],{pix_enabled:true,payment_method:'Cartão'}),/PIX/);
 const t=L.totals([L.line(simple,{quantity:2.01,fillings:['Ninho']})],{pix_enabled:true,pix_percent:3.5});assert.equal(t.pix_discount_cents,528);assert.equal(t.deposit_cents,7274);
});
test('Sinal, saldo, quitação, validade e pagamentos excessivos',()=>{
 const q=quote();assert.equal(L.status(q),'Em Aberto');q.payments.push(L.payment(q,7500,'PIX'));assert.equal(L.status(q),'Aprovado / Data Reservada');assert.equal(q.totals.total_cents-L.paid(q),7500);
 assert.throws(()=>L.payment(q,7501,'Dinheiro'),/saldo/);q.payments.push(L.payment(q,7500,'Dinheiro'));assert.equal(L.status(q),'Quitado / Data Reservada');q.delivered=true;assert.equal(L.status(q),'Entregue');assert.throws(()=>L.payment(q,1,'PIX'));
 const expired=quote();expired.valid_until='2000-01-01';assert.equal(L.status(expired),'Vencido');assert.throws(()=>L.payment(expired,7500,'PIX'),/vencido/);
});
test('Cadastros: CPF, telefone, e-mail e endereço estruturado',()=>{
 const c=L.customer({name:'Maria',phone:'(92) 99999-8888',email:'MARIA@EXAMPLE.COM',cpf:'529.982.247-25',postal_code:'69000-000',street:'Rua A',number:'42',city:'Manaus',state:'AM'});assert.equal(c.phone,'92999998888');assert.equal(c.email,'maria@example.com');assert.ok(L.address(c).includes('Rua A, 42'));assert.equal(c.postal_code,'69000000');
 assert.throws(()=>L.customer({...c,cpf:'11111111111'}),/CPF/);assert.throws(()=>L.customer({...c,email:'invalido'}),/e-mail/);
});
test('Backup rejeita referências de clientes, pagamentos e imagens inválidas',()=>{
 const good={schema:1,settings:{name:'Confeitaria'},products:[],customers:[{id:'c1'}],inventory:[],quotes:[{...quote(),id:'q1',customer_id:'c1'}],images:{}};assert.equal(L.validateBackup(good),good);
 assert.throws(()=>L.validateBackup({...good,customers:[]}),/cliente/);assert.throws(()=>L.validateBackup({...good,images:{p:'https://example.com/foto.png'}}),/imagem/);assert.throws(()=>L.validateBackup({...good,customers:[{id:'c1'},{id:'c1'}]}),/duplicados/);
});
