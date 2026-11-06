using System;
using System.Text.Json;
using MegaCrit.Sts2.Core.Random;
var rows = new System.Collections.Generic.List<object>();
foreach (ulong seed in new ulong[]{0,1,42, 4294967296, ulong.MaxValue}) {
 var rng = new MegaRandom(seed);
 var ints = new int[8]; for(int i=0;i<8;i++) ints[i]=rng.Next(0,2147483647);
 rng=new MegaRandom(seed);
 var doubles=new double[8];for(int i=0;i<8;i++) doubles[i]=rng.NextDouble();
 rng=new MegaRandom(seed);
 var ulongs=new ulong[8];for(int i=0;i<8;i++) ulongs[i]=rng.NextULong();
 rows.Add(new {seed, ints, doubles, ulongs});
}
Console.WriteLine(JsonSerializer.Serialize(rows));
